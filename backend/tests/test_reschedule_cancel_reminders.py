"""4. Bronni ko'chirish, bekor qilish va bekor qilingandan keyin eslatma yuborilmasligi."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings import services as booking_services
from apps.bookings.models import TrialBooking
from apps.conversations import inbound
from apps.conversations.models import Message
from apps.core.exceptions import BusinessError
from apps.leads import services as lead_services
from apps.notifications import services as notif_services
from apps.notifications.models import OutboxMessage, Reminder

pytestmark = pytest.mark.django_db


def test_reschedule_moves_seats_atomically(kit):
    old, new = kit.slot(days=2), kit.slot(days=3)
    lead = kit.lead()
    booking = booking_services.create_trial_booking(kit.org, lead=lead, slot_id=old.id).booking
    booking_services.reschedule_trial_booking(kit.org, booking.id, new.id)
    old.refresh_from_db()
    new.refresh_from_db()
    booking.refresh_from_db()
    assert booking.slot_id == new.id and booking.reschedule_count == 1
    assert old.seats_taken == 0 and new.seats_taken == 1
    assert booking.events.filter(event_type="rescheduled").count() == 1


def test_reschedule_to_full_slot_keeps_old_booking(kit):
    old, full = kit.slot(days=2), kit.slot(days=4, capacity=1)
    booking_services.create_trial_booking(kit.org, lead=kit.lead(), slot_id=full.id)
    lead = kit.lead()
    booking = booking_services.create_trial_booking(kit.org, lead=lead, slot_id=old.id).booking
    with pytest.raises(BusinessError) as exc:
        booking_services.reschedule_trial_booking(kit.org, booking.id, full.id)
    assert exc.value.code == "slot_full"
    booking.refresh_from_db()
    old.refresh_from_db()
    full.refresh_from_db()
    assert booking.slot_id == old.id and booking.status == "confirmed"
    assert old.seats_taken == 1 and full.seats_taken == 1


def test_reschedule_to_past_slot_fails(kit):
    old, past = kit.slot(days=2), kit.slot(days=-1)
    booking = booking_services.create_trial_booking(kit.org, lead=kit.lead(), slot_id=old.id).booking
    with pytest.raises(BusinessError):
        booking_services.reschedule_trial_booking(kit.org, booking.id, past.id)
    booking.refresh_from_db()
    assert booking.slot_id == old.id


def test_cancel_frees_seat_and_cancels_reminder(kit):
    slot = kit.slot(days=2)
    lead = kit.lead(consent_reminders=True)
    booking = booking_services.create_trial_booking(kit.org, lead=lead, slot_id=slot.id).booking
    assert Reminder.objects.filter(booking=booking, status="scheduled").count() == 1
    booking_services.cancel_trial_booking(kit.org, booking.id, reason="test")
    slot.refresh_from_db()
    assert slot.seats_taken == 0
    assert Reminder.objects.filter(booking=booking, status="scheduled").count() == 0
    # Bekor qilish idempotent
    booking_services.cancel_trial_booking(kit.org, booking.id)
    slot.refresh_from_db()
    assert slot.seats_taken == 0


def test_no_reminder_sent_after_cancellation(kit):
    slot = kit.slot(days=1)
    conv = inbound.get_telegram_conversation(kit.org, chat_id=777001, user_id=777001, language="uz")
    lead = conv.lead
    lead_services.set_reminder_consent(lead, True)
    booking = booking_services.create_trial_booking(kit.org, lead=lead, slot_id=slot.id, conversation=conv).booking
    reminder = Reminder.objects.get(booking=booking, status="scheduled")
    # Eslatma vaqtini o'tkazib, bronni bekor qilamiz — keyin dispatch hech narsa yubormasligi kerak
    Reminder.objects.filter(pk=reminder.pk).update(scheduled_for=timezone.now() - timedelta(minutes=1))
    booking_services.cancel_trial_booking(kit.org, booking.id)
    stats = notif_services.dispatch_due_reminders()
    assert stats["sent"] == 0
    assert not OutboxMessage.objects.filter(kind="reminder").exists()
    reminder.refresh_from_db()
    assert reminder.status == "cancelled"


def test_cancelled_booking_skipped_even_if_reminder_left_scheduled(kit):
    slot = kit.slot(days=1)
    conv = inbound.get_telegram_conversation(kit.org, chat_id=777002, user_id=777002)
    lead = conv.lead
    lead_services.set_reminder_consent(lead, True)
    booking = booking_services.create_trial_booking(kit.org, lead=lead, slot_id=slot.id).booking
    # Poyga holati simulyatsiyasi: bron bekor qilingan, eslatma esa "scheduled" qolgan
    TrialBooking.objects.filter(pk=booking.pk).update(status="cancelled")
    Reminder.objects.filter(booking=booking).update(scheduled_for=timezone.now() - timedelta(minutes=1))
    stats = notif_services.dispatch_due_reminders()
    assert stats == {"sent": 0, "skipped": 1, "failed": 0}
    assert not OutboxMessage.objects.filter(kind="reminder").exists()


def test_reminder_sent_for_confirmed_booking_goes_to_demo_outbox(kit):
    slot = kit.slot(days=1)
    conv = inbound.get_telegram_conversation(kit.org, chat_id=777003, user_id=777003)
    lead_services.set_reminder_consent(conv.lead, True)
    booking = booking_services.create_trial_booking(kit.org, lead=conv.lead, slot_id=slot.id, conversation=conv).booking
    Reminder.objects.filter(booking=booking).update(scheduled_for=timezone.now() - timedelta(minutes=1))
    stats = notif_services.dispatch_due_reminders()
    assert stats["sent"] == 1
    item = OutboxMessage.objects.get(kind="reminder")
    assert item.status == "demo"  # DEMO_MODE: real foydalanuvchiga yuborilmaydi
    assert Message.objects.filter(conversation=conv, sender="system", text__contains="Eslatma").exists()
    # Qayta dispatch — takroriy yuborish yo'q
    assert notif_services.dispatch_due_reminders()["sent"] == 0
    assert OutboxMessage.objects.filter(kind="reminder").count() == 1


def test_no_reminder_without_consent(kit):
    slot = kit.slot(days=2)
    booking = booking_services.create_trial_booking(kit.org, lead=kit.lead(consent_reminders=False), slot_id=slot.id).booking
    assert not Reminder.objects.filter(booking=booking).exists()


def test_attendance_only_after_start(kit):
    future = kit.slot(days=1)
    booking = booking_services.create_trial_booking(kit.org, lead=kit.lead(), slot_id=future.id).booking
    with pytest.raises(BusinessError) as exc:
        booking_services.mark_attendance(kit.org, booking.id, attended=True)
    assert exc.value.code == "lesson_not_started"
    TrialBooking.objects.filter(pk=booking.pk).update()
    future.starts_at = timezone.now() - timedelta(hours=1)
    future.ends_at = timezone.now() + timedelta(minutes=30)
    future.save()
    booking_services.mark_attendance(kit.org, booking.id, attended=True)
    booking.refresh_from_db()
    assert booking.status == "attended"
    booking.lead.refresh_from_db()
    assert booking.lead.status == "trial_attended"


def test_api_reschedule_and_cancel(kit, client_for):
    client = client_for(kit.operator)
    s1, s2 = kit.slot(days=2), kit.slot(days=5)
    lead = kit.lead()
    res = client.post("/api/bookings/", {"lead_id": lead.id, "slot_id": s1.id}, format="json")
    assert res.status_code == 201
    bid = res.json()["id"]
    res = client.post(f"/api/bookings/{bid}/reschedule/", {"slot_id": s2.id}, format="json")
    assert res.status_code == 200 and res.json()["slot_id"] == s2.id
    res = client.post(f"/api/bookings/{bid}/cancel/", {"reason": "Mijoz so'radi"}, format="json")
    assert res.status_code == 200 and res.json()["status"] == "cancelled"
    assert [e["event_type"] for e in res.json()["events"]] == ["confirmed", "rescheduled", "cancelled"]
