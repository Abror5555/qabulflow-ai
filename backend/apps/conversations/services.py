"""Suhbat, xabar va operatorga o'tkazish (human handoff) amallari."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.conversations.models import Conversation, HumanHandoff, Message
from apps.core.audit import record_audit
from apps.core.exceptions import BusinessError


@dataclass
class RecordResult:
    message: Message
    duplicate: bool


def touch_conversation(conversation: Conversation, message: Message) -> None:
    preview = (message.text or ("🎤 Ovozli xabar" if message.kind == Message.Kind.VOICE else "")).replace("\n", " ")[:200]
    Conversation.objects.filter(pk=conversation.pk).update(last_message_at=message.created_at, last_message_preview=preview)
    conversation.last_message_at = message.created_at
    conversation.last_message_preview = preview


def record_customer_message(
    conversation: Conversation,
    *,
    text: str = "",
    kind: str = Message.Kind.TEXT,
    external_id: str | None = None,
    language: str = "",
    created_at=None,
) -> RecordResult:
    """Mijoz xabarini saqlaydi. external_id takrorlansa — mavjud xabarni qaytaradi."""

    if external_id:
        existing = Message.objects.filter(conversation=conversation, external_id=external_id).first()
        if existing:
            return RecordResult(existing, True)
    try:
        with transaction.atomic():
            message = Message.objects.create(
                organization_id=conversation.organization_id,
                conversation=conversation,
                sender=Message.Sender.CUSTOMER,
                kind=kind,
                text=(text or "")[:4000],
                language=language or conversation.language,
                external_id=external_id,
                created_at=created_at or timezone.now(),
            )
    except IntegrityError:
        return RecordResult(Message.objects.get(conversation=conversation, external_id=external_id), True)
    touch_conversation(conversation, message)
    lead = conversation.lead
    lead.last_activity_at = message.created_at
    lead.save(update_fields=["last_activity_at"])
    return RecordResult(message, False)


def add_outbound_message(
    conversation: Conversation,
    *,
    sender: str,
    text: str,
    author=None,
    sources=None,
    tool_trace=None,
    is_demo: bool = False,
    ai_status: str = Message.AIStatus.NONE,
    kind: str = Message.Kind.TEXT,
    created_at=None,
) -> Message:
    delivery = Message.Delivery.SENT if conversation.channel in ("webchat", "test") else Message.Delivery.PENDING
    if kind == Message.Kind.EVENT and conversation.channel != "telegram":
        delivery = Message.Delivery.NOT_APPLICABLE
    message = Message.objects.create(
        organization_id=conversation.organization_id,
        conversation=conversation,
        sender=sender,
        author=author,
        kind=kind,
        text=text[:4000],
        language=conversation.language,
        sources=sources or [],
        tool_trace=tool_trace or [],
        is_demo=is_demo,
        ai_status=ai_status,
        delivery_status=delivery,
        created_at=created_at or timezone.now(),
    )
    touch_conversation(conversation, message)
    return message


def deliver_to_channel(conversation: Conversation, message: Message, *, deliver_async: bool = True):
    """Telegram uchun outbox orqali yuboradi (takroriy jo'natishdan himoyalangan)."""

    if conversation.channel != "telegram":
        return None
    from apps.notifications.services import enqueue_outbox

    return enqueue_outbox(
        conversation.organization,
        channel="telegram",
        recipient=conversation.external_chat_id,
        text=message.text,
        dedup_key=f"msg:{message.id}",
        message=message,
        deliver_async=deliver_async,
    )


@transaction.atomic
def request_handoff(conversation: Conversation, *, via: str, reason: str = "") -> HumanHandoff | None:
    conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
    if conversation.mode == Conversation.Mode.HUMAN:
        return conversation.handoffs.exclude(status=HumanHandoff.Status.RETURNED).first()
    conversation.mode = Conversation.Mode.HUMAN
    conversation.needs_attention = True
    conversation.save(update_fields=["mode", "needs_attention", "updated_at"])
    handoff = HumanHandoff.objects.create(organization_id=conversation.organization_id, conversation=conversation, requested_via=via, reason=reason[:255])
    record_audit(
        conversation.organization,
        "conversation.handoff_requested",
        actor_type="ai" if via == "ai" else "customer",
        obj=conversation,
        summary=f"{conversation.lead.display_name}: operator so'raldi",
        metadata={"reason": reason[:120]},
    )
    from apps.notifications.services import notify_staff

    notify_staff(
        conversation.organization,
        "handoff_requested",
        "Mijoz operator kutmoqda",
        f"{conversation.lead.display_name}: {reason[:120]}",
        link=f"/conversations/{conversation.id}",
        branch_id=conversation.lead.branch_id,
    )
    return handoff


@transaction.atomic
def take_over(conversation: Conversation, user) -> Conversation:
    from apps.ai_agent.texts import t

    conversation = Conversation.objects.select_for_update().select_related("lead", "organization").get(pk=conversation.pk)
    was_human = conversation.mode == Conversation.Mode.HUMAN and conversation.assigned_to_id == user.id
    now = timezone.now()
    handoff = conversation.handoffs.filter(status=HumanHandoff.Status.REQUESTED).first()
    if handoff:
        handoff.status = HumanHandoff.Status.ACTIVE
        handoff.taken_by = user
        handoff.taken_at = now
        handoff.save(update_fields=["status", "taken_by", "taken_at"])
    elif not conversation.handoffs.filter(status=HumanHandoff.Status.ACTIVE).exists():
        HumanHandoff.objects.create(
            organization_id=conversation.organization_id,
            conversation=conversation,
            requested_via=HumanHandoff.Via.OPERATOR,
            status=HumanHandoff.Status.ACTIVE,
            taken_by=user,
            taken_at=now,
        )
    conversation.mode = Conversation.Mode.HUMAN
    conversation.assigned_to = user
    conversation.needs_attention = False
    conversation.save(update_fields=["mode", "assigned_to", "needs_attention", "updated_at"])
    if not was_human:
        msg = add_outbound_message(conversation, sender=Message.Sender.SYSTEM, kind=Message.Kind.EVENT, text=t("operator_joined", conversation.language))
        deliver_to_channel(conversation, msg)
        record_audit(
            conversation.organization,
            "conversation.taken_over",
            actor=user,
            obj=conversation,
            summary=f"{user} suhbatni oldi: {conversation.lead.display_name}",
        )
    return conversation


@transaction.atomic
def return_to_ai(conversation: Conversation, user) -> Conversation:
    from apps.ai_agent.texts import t

    conversation = Conversation.objects.select_for_update().select_related("lead", "organization").get(pk=conversation.pk)
    if conversation.mode == Conversation.Mode.AI:
        return conversation
    now = timezone.now()
    conversation.handoffs.exclude(status=HumanHandoff.Status.RETURNED).update(status=HumanHandoff.Status.RETURNED, returned_by=user, returned_at=now)
    conversation.mode = Conversation.Mode.AI
    conversation.needs_attention = False
    state = dict(conversation.state or {})
    state["failed_attempts"] = 0
    conversation.state = state
    conversation.save(update_fields=["mode", "needs_attention", "state", "updated_at"])
    msg = add_outbound_message(conversation, sender=Message.Sender.SYSTEM, kind=Message.Kind.EVENT, text=t("ai_returned", conversation.language))
    deliver_to_channel(conversation, msg)
    record_audit(
        conversation.organization,
        "conversation.returned_to_ai",
        actor=user,
        obj=conversation,
        summary=f"Suhbat AI'ga qaytarildi: {conversation.lead.display_name}",
    )
    return conversation


def operator_reply(conversation: Conversation, user, text: str) -> Message:
    text = (text or "").strip()
    if not text:
        raise BusinessError("empty_message", "Xabar matni bo'sh.", status_code=400)
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().select_related("organization", "lead").get(pk=conversation.pk)
        if conversation.mode != Conversation.Mode.HUMAN:
            raise BusinessError("take_over_required", "Javob yozish uchun avval suhbatni o'zingizga oling (AI to'xtatiladi).")
        msg = add_outbound_message(conversation, sender=Message.Sender.OPERATOR, text=text, author=user)
        if conversation.needs_attention:
            Conversation.objects.filter(pk=conversation.pk).update(needs_attention=False)
        deliver_to_channel(conversation, msg)
    return msg


def close_conversation(conversation: Conversation, user) -> Conversation:
    conversation.status = Conversation.Status.CLOSED
    conversation.needs_attention = False
    conversation.save(update_fields=["status", "needs_attention", "updated_at"])
    record_audit(conversation.organization, "conversation.closed", actor=user, obj=conversation, summary=f"Suhbat yopildi: {conversation.lead.display_name}")
    return conversation
