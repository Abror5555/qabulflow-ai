"""2. Kurs/jadval qidirishdan mijoz tasdig'i bilan bron yaratishgacha to'liq service jarayoni."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.ai_agent.tools import ToolContext, ToolExecutor
from apps.bookings import services as booking_services
from apps.bookings.models import BookingEvent, TrialBooking
from apps.conversations import inbound
from apps.conversations import services as conv_services
from apps.core.exceptions import BusinessError
from apps.leads.models import Lead, LeadStatusChange
from apps.notifications.models import Notification, Reminder

pytestmark = pytest.mark.django_db


def _executor(conversation, text):
    msg = conv_services.record_customer_message(conversation, text=text).message
    return ToolExecutor(ToolContext(conversation=conversation, customer_message=msg))


def test_tool_flow_requires_customer_confirmation(kit):
    slot = kit.slot(days=3)
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_flow_1")
    x = _executor(conv, "IELTS narxi qancha?")
    courses = x.execute("list_courses", {})["courses"]
    ielts = next(c for c in courses if c["name"] == "IELTS Intensive")
    assert ielts["price"] == "1200000"  # narx bazadan
    avail = x.execute("check_trial_availability", {"course_id": ielts["course_id"]})
    assert avail["ok"] and avail["slots"][0]["slot_id"] == slot.id
    x.execute("update_lead", {"full_name": "Aziza", "phone": "+998 00 111 22 33"})

    first = x.execute("create_trial_booking", {"slot_id": slot.id, "customer_confirmed": True})
    assert first["status"] == "confirmation_required"
    assert not TrialBooking.objects.exists()
    conv.save(update_fields=["state"])

    # Tasdiq bo'lmagan javob — bron yaratilmaydi
    x2 = _executor(conv, "balki keyinroq")
    res = x2.execute("create_trial_booking", {"slot_id": slot.id, "customer_confirmed": True})
    assert res["status"] == "confirmation_required"
    assert not TrialBooking.objects.exists()

    x3 = _executor(conv, "Ha")
    ok = x3.execute("create_trial_booking", {"slot_id": slot.id, "customer_confirmed": True})
    assert ok["ok"] is True
    booking = TrialBooking.objects.get()
    assert booking.status == "confirmed" and booking.channel == "webchat" and booking.conversation_id == conv.id
    slot.refresh_from_db()
    assert slot.seats_taken == 1
    lead = Lead.objects.get(pk=conv.lead_id)
    assert lead.status == "trial_booked"
    assert LeadStatusChange.objects.filter(lead=lead, to_status="trial_booked").exists()
    assert BookingEvent.objects.filter(booking=booking, event_type="confirmed").exists()
    assert Notification.objects.filter(organization=kit.org, kind="new_booking").exists()


def test_demo_agent_end_to_end_booking(kit):
    slot = kit.slot(days=2, hour=10)
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_flow_2", language="uz")
    script = ["IELTS kursi narxi qancha?", "Ha, yozilmoqchiman", "ertalab", "1", "Dilnoza", "+998 00 765 43 21", "Ha", "Ha"]
    replies = []
    for text in script:
        result = inbound.process_text(conv, text)
        conv = result.conversation
        replies.append(result.replies[0].text)
    assert "1 200 000" in replies[0]
    assert "Tasdiqlang" in replies[5] or "tasdiqlang" in replies[5]
    assert "yozildingiz" in replies[6]
    booking = TrialBooking.objects.get(lead=conv.lead)
    assert booking.slot_id == slot.id and booking.status == "confirmed"
    lead = Lead.objects.get(pk=conv.lead_id)
    assert lead.full_name == "Dilnoza" and lead.phone == "+998007654321" and lead.consent_reminders
    assert Reminder.objects.filter(booking=booking, status="scheduled").count() == 1
    assert str(booking.id) in replies[6]


def test_no_booking_message_without_successful_tool(kit):
    """Slot to'lgan bo'lsa ham agent 'yozildingiz' demaydi."""

    slot = kit.slot(days=2, capacity=1)
    other = kit.lead()
    booking_services.create_trial_booking(kit.org, lead=other, slot_id=slot.id)
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_flow_3", language="uz")
    for text in ["IELTS sinov darsiga yozilmoqchiman", "ertalab"]:
        result = inbound.process_text(conv, text)
        conv = result.conversation
    assert "yozildingiz" not in result.replies[0].text
    assert TrialBooking.objects.filter(lead=conv.lead).count() == 0


@pytest.mark.parametrize("case", ["past", "inactive_course", "full", "cancelled_slot", "inactive_group"])
def test_invalid_slots_rejected(kit, case):
    lead = kit.lead()
    if case == "past":
        slot = kit.slot(days=-1)
        code = "slot_in_past"
    elif case == "inactive_course":
        slot = kit.slot()
        kit.course.is_active = False
        kit.course.save()
        code = "course_inactive"
    elif case == "inactive_group":
        slot = kit.slot()
        kit.group.is_active = False
        kit.group.save()
        code = "course_inactive"
    elif case == "full":
        slot = kit.slot(capacity=1)
        booking_services.create_trial_booking(kit.org, lead=kit.lead(), slot_id=slot.id)
        code = "slot_full"
    else:
        slot = kit.slot(status="cancelled")
        code = "slot_cancelled"
    with pytest.raises(BusinessError) as exc:
        booking_services.create_trial_booking(kit.org, lead=lead, slot_id=slot.id)
    assert exc.value.code == code


def test_duplicate_booking_same_slot_rejected(kit):
    lead = kit.lead()
    slot = kit.slot(capacity=5)
    booking_services.create_trial_booking(kit.org, lead=lead, slot_id=slot.id)
    with pytest.raises(BusinessError) as exc:
        booking_services.create_trial_booking(kit.org, lead=lead, slot_id=slot.id)
    assert exc.value.code == "already_booked"
    slot.refresh_from_db()
    assert slot.seats_taken == 1


def test_idempotency_key_returns_same_booking(kit, client_for):
    lead = kit.lead()
    slot = kit.slot(capacity=5)
    client = client_for(kit.operator)
    r1 = client.post("/api/bookings/", {"lead_id": lead.id, "slot_id": slot.id}, format="json", HTTP_IDEMPOTENCY_KEY="abc-1")
    r2 = client.post("/api/bookings/", {"lead_id": lead.id, "slot_id": slot.id}, format="json", HTTP_IDEMPOTENCY_KEY="abc-1")
    assert r1.status_code == 201 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert TrialBooking.objects.count() == 1


def test_multi_seat_slot_accepts_different_customers(kit):
    slot = kit.slot(capacity=3)
    for _ in range(3):
        booking_services.create_trial_booking(kit.org, lead=kit.lead(), slot_id=slot.id)
    slot.refresh_from_db()
    assert slot.seats_taken == 3
    with pytest.raises(BusinessError):
        booking_services.create_trial_booking(kit.org, lead=kit.lead(), slot_id=slot.id)


def test_tool_rejects_foreign_booking_ownership(kit):
    slot = kit.slot()
    stranger = kit.lead()
    foreign_booking = booking_services.create_trial_booking(kit.org, lead=stranger, slot_id=slot.id).booking
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_owner")
    x = _executor(conv, "bekor qiling")
    res = x.execute("cancel_trial_booking", {"booking_id": foreign_booking.id})
    assert res["ok"] is False and res["error"] == "booking_not_found"
    foreign_booking.refresh_from_db()
    assert foreign_booking.status == "confirmed"


def test_slot_in_past_not_offered(kit):
    past = kit.slot(days=-2)
    future = kit.slot(days=1)
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_avail")
    x = _executor(conv, "jadval")
    ids = [s["slot_id"] for s in x.execute("check_trial_availability", {"course_id": kit.course.id})["slots"]]
    assert future.id in ids and past.id not in ids
    assert timezone.now() - timedelta(days=1) > past.starts_at
