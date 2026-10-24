"""5. Human handoff'dan keyin AI avtomatik javob bermasligi."""

import pytest

from apps.conversations import inbound
from apps.conversations import services as conv_services
from apps.conversations.models import Conversation, HumanHandoff, Message
from apps.core.exceptions import BusinessError
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


def test_ai_stops_after_take_over_and_resumes_after_return(kit):
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_h1")
    r1 = inbound.process_text(conv, "IELTS narxi qancha?")
    assert len(r1.replies) == 1 and r1.replies[0].sender == "ai"

    conv_services.take_over(conv, kit.operator)
    conv.refresh_from_db()
    assert conv.mode == "human" and conv.assigned_to_id == kit.operator.id

    r2 = inbound.process_text(conv, "Python narxi qancha?")
    assert r2.replies == []
    r2.customer_message.refresh_from_db()
    assert r2.customer_message.ai_status == "skipped_human"
    assert Message.objects.filter(conversation=conv, sender="ai").count() == 1
    conv.refresh_from_db()
    assert conv.needs_attention is True

    msg = conv_services.operator_reply(conv, kit.operator, "Salom, men administrator")
    assert msg.sender == "operator"

    conv_services.return_to_ai(conv, kit.operator)
    conv.refresh_from_db()
    assert conv.mode == "ai"
    r3 = inbound.process_text(conv, "Python narxi qancha?")
    assert len(r3.replies) == 1 and "900 000" in r3.replies[0].text
    assert HumanHandoff.objects.get(conversation=conv).status == "returned"


def test_operator_reply_requires_take_over(kit):
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_h2")
    with pytest.raises(BusinessError) as exc:
        conv_services.operator_reply(conv, kit.operator, "Salom")
    assert exc.value.code == "take_over_required"


def test_customer_request_triggers_handoff_and_notification(kit):
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_h3")
    result = inbound.process_text(conv, "Administrator bilan gaplashmoqchiman")
    conv.refresh_from_db()
    assert conv.mode == "human" and conv.needs_attention
    assert HumanHandoff.objects.filter(conversation=conv, status="requested").exists()
    assert "administrator" in result.replies[0].text.lower()
    assert Notification.objects.filter(organization=kit.org, kind="handoff_requested").exists()
    # Keyingi xabarga AI javob bermaydi
    assert inbound.process_text(conv, "Hali ham kutyapman").replies == []


def test_api_take_over_reply_and_return(kit, client_for):
    conv = inbound.get_webchat_conversation(kit.org, visitor_id="web_h4")
    inbound.process_text(conv, "Salom")
    client = client_for(kit.operator)
    assert client.post(f"/api/conversations/{conv.id}/reply/", {"text": "Salom"}, format="json").status_code == 409
    res = client.post(f"/api/conversations/{conv.id}/take-over/")
    assert res.status_code == 200 and res.json()["mode"] == "human"
    res = client.post(f"/api/conversations/{conv.id}/reply/", {"text": "Salom, qanday yordam bera olaman?"}, format="json")
    assert res.status_code == 201 and res.json()["sender"] == "operator"
    res = client.post(f"/api/conversations/{conv.id}/return-to-ai/")
    assert res.status_code == 200 and res.json()["mode"] == "ai"
    msgs = client.get(f"/api/conversations/{conv.id}/messages/").json()["results"]
    assert [m["sender"] for m in msgs][-3:] == ["system", "operator", "system"]


def test_telegram_operator_reply_goes_to_demo_outbox(kit):
    conv = inbound.get_telegram_conversation(kit.org, chat_id=555, user_id=555)
    inbound.process_text(conv, "Salom")
    conv_services.take_over(conv, kit.operator)
    msg = conv_services.operator_reply(conv, kit.operator, "Assalomu alaykum")
    msg.refresh_from_db()
    assert msg.delivery_status == "demo"
    assert msg.outbox_items.get().status == "demo"
    assert Conversation.objects.get(pk=conv.pk).mode == "human"
