from celery import shared_task
from django.utils import timezone

from apps.notifications import services
from apps.notifications.models import OutboxMessage


@shared_task(name="apps.notifications.tasks.deliver_outbox_message", autoretry_for=(), ignore_result=True)
def deliver_outbox_message(outbox_id: int) -> str:
    item = services.deliver_outbox(outbox_id)
    return item.status


@shared_task(name="apps.notifications.tasks.dispatch_due_reminders", ignore_result=True)
def dispatch_due_reminders() -> dict:
    return services.dispatch_due_reminders()


@shared_task(name="apps.notifications.tasks.retry_pending_outbox", ignore_result=True)
def retry_pending_outbox() -> int:
    """Navbatda qolib ketgan yoki vaqtinchalik xato bo'lgan xabarlarni qayta urinish."""

    cutoff = timezone.now() - timezone.timedelta(minutes=1)
    ids = list(
        OutboxMessage.objects.filter(status=OutboxMessage.Status.QUEUED, created_at__lte=cutoff, attempts__lt=services.MAX_OUTBOX_ATTEMPTS).values_list(
            "id", flat=True
        )[:50]
    )
    for outbox_id in ids:
        services.deliver_outbox(outbox_id)
    return len(ids)
