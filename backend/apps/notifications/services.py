"""Bildirishnomalar, eslatmalar va tashqi xabarlar navbati (outbox)."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.logging import redact
from apps.core.permissions import ROLE_LEVEL
from apps.notifications.models import Notification, OutboxMessage, Reminder

logger = logging.getLogger(__name__)

MAX_OUTBOX_ATTEMPTS = 5


# --------------------------------------------------------------------------- staff
def notify_staff(organization, kind: str, title: str, body: str = "", link: str = "", *, min_role: str = "operator", branch_id=None) -> int:
    from apps.organizations.models import Membership

    memberships = Membership.objects.filter(organization=organization, is_active=True, user__is_active=True).select_related("user").prefetch_related("branches")
    items = []
    for m in memberships:
        if ROLE_LEVEL.get(m.role, 0) < ROLE_LEVEL[min_role]:
            continue
        prefs = m.get_notification_prefs()
        if kind in prefs and not prefs[kind]:
            continue
        if branch_id and m.role != "owner":
            allowed = [b.id for b in m.branches.all()]
            if allowed and branch_id not in allowed:
                continue
        items.append(Notification(organization=organization, user=m.user, kind=kind, title=title[:160], body=body[:500], link=link[:200]))
    Notification.objects.bulk_create(items)
    return len(items)


# --------------------------------------------------------------------------- outbox
def telegram_sending_enabled() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN) and not settings.DEMO_MODE


def enqueue_outbox(
    organization, *, channel: str, recipient: str, text: str, dedup_key: str, kind: str = OutboxMessage.Kind.REPLY, message=None, deliver_async: bool = True
) -> OutboxMessage:
    """Takroriy jo'natishdan himoyalangan holda xabarni navbatga qo'yadi."""

    demo = channel == "telegram" and not telegram_sending_enabled()
    defaults = {
        "organization": organization,
        "channel": channel,
        "recipient": str(recipient),
        "text": text,
        "kind": kind,
        "message": message,
        "status": OutboxMessage.Status.DEMO if demo else OutboxMessage.Status.QUEUED,
    }
    try:
        with transaction.atomic():
            item, created = OutboxMessage.objects.get_or_create(dedup_key=dedup_key, defaults=defaults)
    except IntegrityError:
        item, created = OutboxMessage.objects.get(dedup_key=dedup_key), False
    if message is not None and created:
        message.delivery_status = "demo" if demo else "pending"
        message.save(update_fields=["delivery_status"])
    if created and not demo and deliver_async:
        from apps.notifications.tasks import deliver_outbox_message

        transaction.on_commit(lambda: deliver_outbox_message.delay(item.id))
    return item


def deliver_outbox(outbox_id: int, *, sender=None) -> OutboxMessage:
    """Navbatdagi xabarni yuboradi. sent/demo bo'lsa qayta yubormaydi."""

    with transaction.atomic():
        item = OutboxMessage.objects.select_for_update().get(pk=outbox_id)
        if item.status in (OutboxMessage.Status.SENT, OutboxMessage.Status.DEMO):
            return item
        if item.attempts >= MAX_OUTBOX_ATTEMPTS:
            item.status = OutboxMessage.Status.FAILED
            item.save(update_fields=["status"])
            return item
        if item.channel == "telegram" and not telegram_sending_enabled():
            item.status = OutboxMessage.Status.DEMO
            item.save(update_fields=["status"])
            return item
        item.status = OutboxMessage.Status.SENDING
        item.attempts += 1
        item.save(update_fields=["status", "attempts"])

    try:
        if item.channel == "telegram":
            if sender is None:
                from apps.integrations.telegram.sender import send_telegram_text

                sender = send_telegram_text
            external_id = sender(item.recipient, item.text)
        else:
            external_id = ""
        item.status = OutboxMessage.Status.SENT
        item.sent_at = timezone.now()
        item.external_message_id = str(external_id or "")
        item.last_error = ""
    except Exception as exc:  # noqa: BLE001
        item.status = OutboxMessage.Status.FAILED if item.attempts >= MAX_OUTBOX_ATTEMPTS else OutboxMessage.Status.QUEUED
        item.last_error = redact(f"{exc.__class__.__name__}: {exc}")[:255]
        logger.warning("Outbox #%s yuborilmadi: %s", item.id, item.last_error)
    item.save(update_fields=["status", "sent_at", "external_message_id", "last_error"])
    if item.message_id:
        from apps.conversations.models import Message

        Message.objects.filter(pk=item.message_id).update(delivery_status={"sent": "sent", "failed": "failed", "queued": "pending"}.get(item.status, "pending"))
    return item


# --------------------------------------------------------------------------- reminders
def cancel_reminders_for_booking(booking) -> int:
    return Reminder.objects.filter(booking=booking, status=Reminder.Status.SCHEDULED).update(status=Reminder.Status.CANCELLED)


def schedule_reminder_for_booking(booking, *, now=None) -> Reminder | None:
    """Mijoz roziligi bo'lsa va bron tasdiqlangan bo'lsa eslatma rejalashtiradi."""

    from apps.ai_agent.services import get_ai_settings

    now = now or timezone.now()
    cancel_reminders_for_booking(booking)
    lead = booking.lead
    if booking.status != "confirmed" or not lead.consent_reminders or lead.is_test:
        return None
    starts_at = booking.slot.starts_at
    if starts_at <= now + timedelta(minutes=15):
        return None
    hours = get_ai_settings(booking.organization).reminder_hours_before
    scheduled_for = starts_at - timedelta(hours=hours)
    if scheduled_for < now:
        scheduled_for = now
    return Reminder.objects.create(organization=booking.organization, booking=booking, scheduled_for=scheduled_for)


def reschedule_reminders_for_lead(lead) -> None:
    from apps.bookings.models import TrialBooking

    now = timezone.now()
    for booking in TrialBooking.objects.filter(lead=lead, status="confirmed", slot__starts_at__gt=now).select_related("slot", "lead"):
        schedule_reminder_for_booking(booking, now=now)


def build_reminder_text(booking) -> str:
    from apps.ai_agent.texts import format_slot_time, t

    lead = booking.lead
    lang = lead.language or "uz"
    slot = booking.slot
    return t(
        "reminder",
        lang,
        course=slot.group.course.name,
        when=format_slot_time(slot.starts_at, booking.organization, lang),
        branch=slot.group.branch.name,
        address=slot.group.branch.address or "",
    )


def dispatch_due_reminders(*, now=None, sender=None) -> dict:
    """Vaqti kelgan eslatmalarni yuboradi. Bekor qilingan bron uchun yubormaydi."""

    from apps.conversations.models import Conversation, Message

    now = now or timezone.now()
    stats = {"sent": 0, "skipped": 0, "failed": 0}
    with transaction.atomic():
        due = list(
            Reminder.objects.select_for_update(skip_locked=True)
            .filter(status=Reminder.Status.SCHEDULED, scheduled_for__lte=now)
            .select_related("booking__lead", "booking__slot__group__course", "booking__slot__group__branch", "booking__organization")[:100]
        )
        for reminder in due:
            booking = reminder.booking
            reminder.attempts += 1
            if booking.status != "confirmed" or not booking.lead.consent_reminders or booking.slot.starts_at <= now:
                reminder.status = Reminder.Status.SKIPPED
                reminder.save(update_fields=["status", "attempts"])
                stats["skipped"] += 1
                continue
            conversation = Conversation.objects.filter(lead=booking.lead).exclude(channel="test").order_by("-last_message_at").first()
            if conversation is None:
                reminder.status = Reminder.Status.SKIPPED
                reminder.last_error = "Mijoz bilan kanal topilmadi"
                reminder.save(update_fields=["status", "attempts", "last_error"])
                stats["skipped"] += 1
                continue
            text = build_reminder_text(booking)
            msg = Message.objects.create(
                organization=booking.organization,
                conversation=conversation,
                sender=Message.Sender.SYSTEM,
                kind=Message.Kind.TEXT,
                text=text,
                language=booking.lead.language,
                delivery_status="sent" if conversation.channel == "webchat" else "pending",
            )
            if conversation.channel == "telegram":
                enqueue_outbox(
                    booking.organization,
                    channel="telegram",
                    recipient=conversation.external_chat_id,
                    text=text,
                    kind=OutboxMessage.Kind.REMINDER,
                    dedup_key=f"reminder:{reminder.id}",
                    message=msg,
                )
            reminder.status = Reminder.Status.SENT
            reminder.sent_at = now
            reminder.save(update_fields=["status", "attempts", "sent_at"])
            stats["sent"] += 1
    return stats
