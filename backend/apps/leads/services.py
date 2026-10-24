"""Lead (mijoz) bilan bog'liq biznes amallari. Barcha kanallar shu qatlamdan foydalanadi."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.audit import record_audit
from apps.core.exceptions import BusinessError
from apps.core.utils import normalize_phone
from apps.leads.models import Lead, LeadNote, LeadStatusChange

UPDATABLE_FIELDS = {
    "full_name",
    "phone",
    "phone_verified",
    "goal",
    "level",
    "preferred_time",
    "branch",
    "interested_course",
    "language",
    "assigned_to",
    "source",
    "telegram_username",
}


def _status_index(status: str) -> int:
    try:
        return Lead.STATUS_ORDER.index(status)
    except ValueError:
        return -1


def create_lead(
    organization,
    *,
    source: str,
    full_name: str = "",
    phone: str = "",
    telegram_user_id: int | None = None,
    telegram_username: str = "",
    language: str = "uz",
    branch=None,
    interested_course=None,
    actor=None,
    via: str = "system",
    is_test: bool = False,
    created_at=None,
    notify: bool = True,
) -> Lead:
    if phone:
        normalized = normalize_phone(phone)
        if not normalized:
            raise BusinessError("invalid_phone", "Telefon raqami noto'g'ri formatda.", status_code=400)
        phone = normalized
    created_at = created_at or timezone.now()
    lead = Lead.objects.create(
        organization=organization,
        source=source,
        full_name=full_name.strip()[:150],
        phone=phone,
        telegram_user_id=telegram_user_id,
        telegram_username=telegram_username[:64],
        language=language,
        branch=branch,
        interested_course=interested_course,
        is_test=is_test,
        created_at=created_at,
        last_activity_at=created_at,
    )
    LeadStatusChange.objects.create(lead=lead, from_status="", to_status=Lead.Status.NEW, changed_by=actor, changed_via=via, created_at=created_at)
    if not is_test:
        record_audit(
            organization,
            "lead.created",
            actor=actor,
            actor_type="user" if actor else ("ai" if via == "ai" else "customer"),
            obj=lead,
            summary=f"Yangi mijoz: {lead.display_name} ({lead.get_source_display()})",
            created_at=created_at,
        )
        if notify:
            from apps.notifications.services import notify_staff

            notify_staff(organization, "new_lead", "Yangi mijoz", lead.display_name, link=f"/leads/{lead.id}")
    return lead


def get_or_create_telegram_lead(organization, *, telegram_user_id: int, username: str = "", full_name: str = "", language: str = "uz") -> tuple[Lead, bool]:
    """Telegram foydalanuvchisini FAQAT tashkilot ichidagi telegram_user_id bo'yicha bog'laydi.

    Ism yoki tasdiqlanmagan telefon bo'yicha boshqa kanal leadlari bilan birlashtirilmaydi.
    """

    existing = Lead.objects.filter(organization=organization, telegram_user_id=telegram_user_id).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            lead = create_lead(
                organization,
                source=Lead.Source.TELEGRAM,
                telegram_user_id=telegram_user_id,
                telegram_username=username or "",
                full_name=full_name or "",
                language=language,
                via="ai",
            )
        return lead, True
    except IntegrityError:
        return Lead.objects.get(organization=organization, telegram_user_id=telegram_user_id), False


def change_status(lead: Lead, new_status: str, *, actor=None, via: str = "operator", reason: str = "", at=None) -> Lead:
    if new_status not in Lead.Status.values:
        raise BusinessError("invalid_status", "Noma'lum holat.", status_code=400)
    if lead.status == new_status:
        return lead
    at = at or timezone.now()
    old = lead.status
    lead.status = new_status
    lead.last_activity_at = at
    lead.save(update_fields=["status", "last_activity_at", "updated_at"])
    LeadStatusChange.objects.create(lead=lead, from_status=old, to_status=new_status, changed_by=actor, changed_via=via, reason=reason[:255], created_at=at)
    if not lead.is_test:
        record_audit(
            lead.organization,
            "lead.status_changed",
            actor=actor,
            actor_type="user" if actor else ("ai" if via == "ai" else "system"),
            obj=lead,
            summary=f"{lead.display_name}: {Lead.Status(old).label if old else '—'} → {Lead.Status(new_status).label}",
            metadata={"from": old, "to": new_status},
            created_at=at,
        )
    return lead


def advance_status(lead: Lead, target: str, *, actor=None, via: str = "system", reason: str = "", at=None) -> Lead:
    """Holatni faqat oldinga siljitadi (yo'qotilgan leadni qayta faollashtiradi)."""

    if lead.status == Lead.Status.LOST or _status_index(target) > _status_index(lead.status):
        return change_status(lead, target, actor=actor, via=via, reason=reason, at=at)
    return lead


def update_lead(lead: Lead, data: dict, *, actor=None, via: str = "operator") -> Lead:
    changed = []
    for field, value in data.items():
        if field not in UPDATABLE_FIELDS:
            continue
        if field == "phone":
            value = (value or "").strip()
            if value:
                normalized = normalize_phone(value)
                if not normalized:
                    raise BusinessError("invalid_phone", "Telefon raqami noto'g'ri formatda. Masalan: +998 90 123 45 67", status_code=400)
                value = normalized
            if value != lead.phone and "phone_verified" not in data:
                lead.phone_verified = False
                changed.append("phone_verified")
        if field in {"branch", "interested_course"} and value is not None and value.organization_id != lead.organization_id:
            raise BusinessError("cross_tenant", "Yozuv topilmadi.", status_code=404)
        if field == "assigned_to" and value is not None:
            if not value.memberships.filter(organization=lead.organization, is_active=True).exists():
                raise BusinessError("invalid_assignee", "Xodim bu tashkilotga a'zo emas.", status_code=400)
        if field == "full_name":
            value = (value or "").strip()[:150]
        setattr(lead, field, value)
        changed.append(field)
    if changed:
        lead.last_activity_at = timezone.now()
        lead.save(update_fields=list(set(changed)) + ["last_activity_at", "updated_at"])
        if lead.status == Lead.Status.NEW and (lead.interested_course_id or lead.goal):
            advance_status(lead, Lead.Status.QUALIFIED, actor=actor, via=via, reason="Ehtiyoj aniqlandi")
    return lead


def set_reminder_consent(lead: Lead, consent: bool) -> Lead:
    from apps.notifications.services import cancel_reminders_for_booking, reschedule_reminders_for_lead

    lead.consent_reminders = consent
    lead.consent_at = timezone.now() if consent else None
    lead.save(update_fields=["consent_reminders", "consent_at", "updated_at"])
    if consent:
        reschedule_reminders_for_lead(lead)
    else:
        for booking in lead.trial_bookings.filter(status="confirmed"):
            cancel_reminders_for_booking(booking)
    return lead


def add_note(lead: Lead, text: str, author) -> LeadNote:
    text = (text or "").strip()
    if not text:
        raise BusinessError("empty_note", "Eslatma matni bo'sh.", status_code=400)
    note = LeadNote.objects.create(lead=lead, author=author, text=text[:4000])
    record_audit(lead.organization, "lead.note_added", actor=author, obj=lead, summary=f"{lead.display_name}: yangi eslatma")
    return note
