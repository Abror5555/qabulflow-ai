"""Sinov darsi bronlari: yaratish, ko'chirish, bekor qilish, qatnashuv.

Sig'im himoyasi:
  * slot qatori SELECT ... FOR UPDATE bilan qulflanadi (bir vaqtdagi so'rovlar navbatga turadi);
  * DB CHECK constraint seats_taken <= capacity;
  * (slot, lead) bo'yicha faol bron uchun partial unique constraint;
  * idempotency_key bo'yicha unique constraint (retry takroriy bron yaratmaydi).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.bookings.models import BookingEvent, Enrollment, TrialBooking
from apps.core.audit import record_audit
from apps.core.exceptions import BusinessError
from apps.courses.models import TrialSlot
from apps.leads import services as lead_services
from apps.leads.models import Lead


@dataclass
class BookingResult:
    booking: TrialBooking
    created: bool


def _lock_slot(organization, slot_id) -> TrialSlot:
    try:
        return TrialSlot.objects.select_for_update(of=("self",)).select_related("group__course", "group__branch").get(organization=organization, pk=slot_id)
    except (TrialSlot.DoesNotExist, ValueError, TypeError):
        raise BusinessError("slot_not_found", "Sinov darsi vaqti topilmadi.", status_code=404) from None


def validate_slot_bookable(slot: TrialSlot, *, now=None) -> None:
    now = now or timezone.now()
    if slot.status != TrialSlot.Status.OPEN:
        raise BusinessError("slot_cancelled", "Bu sinov darsi bekor qilingan.")
    if slot.starts_at <= now:
        raise BusinessError("slot_in_past", "Bu vaqt allaqachon o'tib ketgan.")
    group = slot.group
    if not group.is_active or not group.course.is_active:
        raise BusinessError("course_inactive", "Bu kurs yoki guruh hozir faol emas.")
    if not group.branch.is_active:
        raise BusinessError("branch_inactive", "Bu filial hozir faol emas.")
    if slot.seats_taken >= slot.capacity:
        raise BusinessError("slot_full", "Bu vaqtda bo'sh joy qolmadi.")


def _actor_kind(actor, actor_type):
    return actor_type or ("user" if actor else "system")


@transaction.atomic
def create_trial_booking(
    organization,
    *,
    lead: Lead,
    slot_id,
    channel: str = TrialBooking.Channel.PANEL,
    idempotency_key: str | None = None,
    conversation=None,
    actor=None,
    actor_type: str | None = None,
    notes: str = "",
    now=None,
) -> BookingResult:
    now = now or timezone.now()
    if lead.organization_id != organization.id:
        raise BusinessError("lead_not_found", "Mijoz topilmadi.", status_code=404)
    if lead.is_test:
        raise BusinessError("test_lead", "Test-chat mijozi uchun haqiqiy bron yaratilmaydi.", status_code=400)

    slot = _lock_slot(organization, slot_id)

    # Idempotency: qulf olingandan keyin tekshiriladi (parallel retry ham shu yerda to'xtaydi)
    if idempotency_key:
        existing = TrialBooking.objects.filter(organization=organization, idempotency_key=idempotency_key).first()
        if existing:
            if existing.lead_id != lead.id or existing.slot_id != slot.id:
                raise BusinessError("idempotency_conflict", "Bu so'rov kaliti boshqa bron uchun ishlatilgan.", status_code=409)
            return BookingResult(existing, False)

    duplicate = TrialBooking.objects.filter(slot=slot, lead=lead).exclude(status=TrialBooking.Status.CANCELLED).first()
    if duplicate:
        raise BusinessError("already_booked", "Mijoz bu sinov darsiga allaqachon yozilgan.", details={"booking_id": duplicate.id})

    validate_slot_bookable(slot, now=now)

    TrialSlot.objects.filter(pk=slot.pk).update(seats_taken=F("seats_taken") + 1)
    try:
        with transaction.atomic():
            booking = TrialBooking.objects.create(
                organization=organization,
                lead=lead,
                slot=slot,
                conversation=conversation,
                channel=channel,
                idempotency_key=idempotency_key,
                status=TrialBooking.Status.CONFIRMED,
                confirmed_at=now,
                created_by=actor,
                notes=notes[:255],
                created_at=now,
            )
    except IntegrityError:
        raise BusinessError("already_booked", "Mijoz bu sinov darsiga allaqachon yozilgan.") from None

    BookingEvent.objects.create(
        organization=organization,
        booking=booking,
        event_type=BookingEvent.Type.CONFIRMED,
        to_slot=slot,
        actor=actor,
        actor_type=_actor_kind(actor, actor_type),
        occurred_at=now,
    )
    if lead.branch_id is None:
        lead.branch = slot.group.branch
        lead.save(update_fields=["branch", "updated_at"])
    if lead.interested_course_id is None:
        lead.interested_course = slot.group.course
        lead.save(update_fields=["interested_course", "updated_at"])
    lead_services.advance_status(
        lead,
        Lead.Status.TRIAL_BOOKED,
        actor=actor,
        via="ai" if actor_type == "ai" else ("operator" if actor else "system"),
        reason="Sinov darsiga yozildi",
        at=now,
    )
    record_audit(
        organization,
        "booking.confirmed",
        actor=actor,
        actor_type=_actor_kind(actor, actor_type),
        obj=booking,
        summary=f"{lead.display_name} — {slot.group.course.name}, {timezone.localtime(slot.starts_at):%d.%m %H:%M}",
        created_at=now,
    )

    # Eslatma va panel bildirishnomasi — DB yozuvlari, shu tranzaksiya ichida (bron bekor bo'lsa, ular ham bo'lmaydi)
    from apps.notifications.services import notify_staff, schedule_reminder_for_booking

    schedule_reminder_for_booking(booking, now=now)
    notify_staff(
        organization,
        "new_booking",
        "Yangi sinov darsi broni",
        f"{lead.display_name} — {slot.group.course.name}",
        link=f"/bookings?booking={booking.id}",
        branch_id=slot.group.branch_id,
    )
    slot.refresh_from_db(fields=["seats_taken"])
    return BookingResult(booking, True)


def _get_booking_for_update(organization, booking_id, *, lead: Lead | None = None) -> TrialBooking:
    try:
        booking = (
            TrialBooking.objects.select_for_update(of=("self",))
            .select_related("lead", "slot__group__course", "slot__group__branch")
            .get(organization=organization, pk=booking_id)
        )
    except (TrialBooking.DoesNotExist, ValueError, TypeError):
        raise BusinessError("booking_not_found", "Bron topilmadi.", status_code=404) from None
    if lead is not None and booking.lead_id != lead.id:
        # Egalik tekshiruvi: boshqa mijoz broni haqida ma'lumot oshkor qilinmaydi
        raise BusinessError("booking_not_found", "Bron topilmadi.", status_code=404)
    return booking


@transaction.atomic
def cancel_trial_booking(
    organization, booking_id, *, actor=None, actor_type: str | None = None, reason: str = "", lead: Lead | None = None, now=None
) -> TrialBooking:
    now = now or timezone.now()
    booking = _get_booking_for_update(organization, booking_id, lead=lead)
    if booking.status == TrialBooking.Status.CANCELLED:
        return booking
    if booking.status in (TrialBooking.Status.ATTENDED, TrialBooking.Status.NO_SHOW):
        raise BusinessError("booking_finished", "O'tib ketgan sinov darsini bekor qilib bo'lmaydi.")
    TrialSlot.objects.select_for_update().filter(pk=booking.slot_id).update(seats_taken=F("seats_taken") - 1)
    booking.status = TrialBooking.Status.CANCELLED
    booking.cancelled_at = now
    booking.cancel_reason = reason[:255]
    booking.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    BookingEvent.objects.create(
        organization=organization,
        booking=booking,
        event_type=BookingEvent.Type.CANCELLED,
        from_slot=booking.slot,
        actor=actor,
        actor_type=_actor_kind(actor, actor_type),
        reason=reason[:255],
        occurred_at=now,
    )
    from apps.notifications.services import cancel_reminders_for_booking, notify_staff

    cancel_reminders_for_booking(booking)
    lead = booking.lead
    still_active = lead.trial_bookings.filter(status=TrialBooking.Status.CONFIRMED).exists()
    if not still_active and lead.status == Lead.Status.TRIAL_BOOKED:
        lead_services.change_status(
            lead, Lead.Status.QUALIFIED, actor=actor, via="ai" if actor_type == "ai" else "operator", reason="Bron bekor qilindi", at=now
        )
    record_audit(
        organization,
        "booking.cancelled",
        actor=actor,
        actor_type=_actor_kind(actor, actor_type),
        obj=booking,
        summary=f"{lead.display_name} — bron bekor qilindi",
        created_at=now,
    )
    notify_staff(
        organization,
        "booking_cancelled",
        "Bron bekor qilindi",
        f"{lead.display_name} — {booking.slot.group.course.name}",
        link=f"/bookings?booking={booking.id}",
        branch_id=booking.slot.group.branch_id,
    )
    return booking


@transaction.atomic
def reschedule_trial_booking(
    organization, booking_id, new_slot_id, *, actor=None, actor_type: str | None = None, lead: Lead | None = None, now=None
) -> TrialBooking:
    """Atomar ko'chirish: yangi joy olinmasa, eski bron o'zgarmaydi (tranzaksiya bekor qilinadi)."""

    now = now or timezone.now()
    booking = _get_booking_for_update(organization, booking_id, lead=lead)
    if booking.status != TrialBooking.Status.CONFIRMED:
        raise BusinessError("booking_not_active", "Faqat tasdiqlangan bronni ko'chirish mumkin.")
    try:
        new_slot_id = int(new_slot_id)
    except (TypeError, ValueError):
        raise BusinessError("slot_not_found", "Sinov darsi vaqti topilmadi.", status_code=404) from None
    if new_slot_id == booking.slot_id:
        raise BusinessError("same_slot", "Bron allaqachon shu vaqtda.", status_code=400)

    # Deadlock oldini olish: slotlar doim id tartibida qulflanadi
    ids = sorted([booking.slot_id, new_slot_id])
    locked = {
        s.id: s
        for s in TrialSlot.objects.select_for_update(of=("self",))
        .select_related("group__course", "group__branch")
        .filter(organization=organization, pk__in=ids)
        .order_by("id")
    }
    if new_slot_id not in locked:
        raise BusinessError("slot_not_found", "Sinov darsi vaqti topilmadi.", status_code=404)
    old_slot, new_slot = locked[booking.slot_id], locked[new_slot_id]
    validate_slot_bookable(new_slot, now=now)
    if TrialBooking.objects.filter(slot=new_slot, lead=booking.lead).exclude(status=TrialBooking.Status.CANCELLED).exists():
        raise BusinessError("already_booked", "Mijoz bu vaqtga allaqachon yozilgan.")

    TrialSlot.objects.filter(pk=new_slot.pk).update(seats_taken=F("seats_taken") + 1)
    TrialSlot.objects.filter(pk=old_slot.pk).update(seats_taken=F("seats_taken") - 1)
    booking.slot = new_slot
    booking.reschedule_count += 1
    booking.save(update_fields=["slot", "reschedule_count", "updated_at"])
    BookingEvent.objects.create(
        organization=organization,
        booking=booking,
        event_type=BookingEvent.Type.RESCHEDULED,
        from_slot=old_slot,
        to_slot=new_slot,
        actor=actor,
        actor_type=_actor_kind(actor, actor_type),
        occurred_at=now,
    )
    record_audit(
        organization,
        "booking.rescheduled",
        actor=actor,
        actor_type=_actor_kind(actor, actor_type),
        obj=booking,
        summary=f"{booking.lead.display_name} — {timezone.localtime(new_slot.starts_at):%d.%m %H:%M} ga ko'chirildi",
        created_at=now,
    )
    from apps.notifications.services import schedule_reminder_for_booking

    booking.refresh_from_db()
    schedule_reminder_for_booking(booking, now=now)
    return booking


@transaction.atomic
def mark_attendance(organization, booking_id, *, attended: bool, actor=None, now=None) -> TrialBooking:
    now = now or timezone.now()
    booking = _get_booking_for_update(organization, booking_id)
    if booking.status == TrialBooking.Status.CANCELLED:
        raise BusinessError("booking_cancelled", "Bekor qilingan bron uchun qatnashuv belgilanmaydi.")
    if booking.slot.starts_at > now:
        raise BusinessError("lesson_not_started", "Dars hali boshlanmagan. Qatnashuvni dars boshlangandan keyin belgilang.")
    new_status = TrialBooking.Status.ATTENDED if attended else TrialBooking.Status.NO_SHOW
    if booking.status == new_status:
        return booking
    booking.status = new_status
    booking.attendance_marked_at = now
    booking.save(update_fields=["status", "attendance_marked_at", "updated_at"])
    BookingEvent.objects.create(
        organization=organization,
        booking=booking,
        event_type=BookingEvent.Type.ATTENDED if attended else BookingEvent.Type.NO_SHOW,
        actor=actor,
        actor_type=_actor_kind(actor, None),
        occurred_at=now,
    )
    from apps.notifications.services import cancel_reminders_for_booking

    cancel_reminders_for_booking(booking)
    if attended:
        lead_services.advance_status(booking.lead, Lead.Status.TRIAL_ATTENDED, actor=actor, via="operator", reason="Sinov darsiga keldi", at=now)
    record_audit(
        organization,
        "booking.attended" if attended else "booking.no_show",
        actor=actor,
        obj=booking,
        summary=f"{booking.lead.display_name} — {'qatnashdi' if attended else 'kelmadi'}",
        created_at=now,
    )
    return booking


@transaction.atomic
def confirm_enrollment(organization, *, lead: Lead, course, group=None, actor=None, notes: str = "", now=None) -> Enrollment:
    """Administrator mijozni "o'qishga yozildi" deb tasdiqlaydi."""

    now = now or timezone.now()
    if lead.organization_id != organization.id or course.organization_id != organization.id:
        raise BusinessError("not_found", "Yozuv topilmadi.", status_code=404)
    if group is not None and (group.organization_id != organization.id or group.course_id != course.id):
        raise BusinessError("invalid_group", "Guruh tanlangan kursga tegishli emas.", status_code=400)
    enrollment = Enrollment.objects.select_for_update().filter(lead=lead, course=course).exclude(status=Enrollment.Status.CANCELLED).first()
    if enrollment and enrollment.status == Enrollment.Status.CONFIRMED:
        return enrollment
    if enrollment is None:
        enrollment = Enrollment(organization=organization, lead=lead, course=course, created_at=now)
    enrollment.group = group
    enrollment.status = Enrollment.Status.CONFIRMED
    enrollment.confirmed_by = actor
    enrollment.confirmed_at = now
    enrollment.notes = notes[:255]
    enrollment.save()
    if group is not None:
        type(group).objects.filter(pk=group.pk).update(enrolled_count=F("enrolled_count") + 1)
    lead_services.advance_status(lead, Lead.Status.ENROLLED, actor=actor, via="operator", reason="O'qishga yozildi", at=now)
    record_audit(
        organization, "enrollment.confirmed", actor=actor, obj=enrollment, summary=f"{lead.display_name} — {course.name} kursiga yozildi", created_at=now
    )
    return enrollment


@transaction.atomic
def cancel_enrollment(organization, enrollment_id, *, actor=None) -> Enrollment:
    try:
        enrollment = Enrollment.objects.select_for_update().get(organization=organization, pk=enrollment_id)
    except Enrollment.DoesNotExist:
        raise BusinessError("not_found", "Yozuv topilmadi.", status_code=404) from None
    if enrollment.status == Enrollment.Status.CANCELLED:
        return enrollment
    was_confirmed = enrollment.status == Enrollment.Status.CONFIRMED
    enrollment.status = Enrollment.Status.CANCELLED
    enrollment.save(update_fields=["status", "updated_at"])
    if was_confirmed and enrollment.group_id:
        type(enrollment.group).objects.filter(pk=enrollment.group_id, enrolled_count__gt=0).update(enrolled_count=F("enrolled_count") - 1)
    record_audit(organization, "enrollment.cancelled", actor=actor, obj=enrollment, summary=f"{enrollment.lead.display_name} — o'qishga yozilish bekor qilindi")
    return enrollment
