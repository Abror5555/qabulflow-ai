import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Conversation(TimeStampedModel):
    class Channel(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        WEBCHAT = "webchat", "Veb-chat"
        TEST = "test", "AI test-chat"

    class Status(models.TextChoices):
        OPEN = "open", "Ochiq"
        CLOSED = "closed", "Yopilgan"

    class Mode(models.TextChoices):
        AI = "ai", "AI javob beradi"
        HUMAN = "human", "Operator"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="conversations")
    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="conversations")
    channel = models.CharField(max_length=16, choices=Channel.choices)
    external_chat_id = models.CharField(max_length=128)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.AI)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_conversations")
    language = models.CharField(max_length=2, default="uz", choices=settings.LANGUAGES)
    language_locked = models.BooleanField(default=False, help_text="Mijoz tilni qo'lda tanlagan")
    state = models.JSONField(default=dict, blank=True, help_text="AI dialog holati (bazadan tiklanadi)")
    needs_attention = models.BooleanField(default=False)
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_message_preview = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-last_message_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "channel", "external_chat_id"], name="uniq_conversation_per_chat"),
        ]
        indexes = [models.Index(fields=["organization", "created_at"])]

    def __str__(self) -> str:
        return f"{self.get_channel_display()} #{self.pk}"


class Message(models.Model):
    class Sender(models.TextChoices):
        CUSTOMER = "customer", "Mijoz"
        AI = "ai", "AI"
        OPERATOR = "operator", "Operator"
        SYSTEM = "system", "Tizim"

    class Kind(models.TextChoices):
        TEXT = "text", "Matn"
        VOICE = "voice", "Ovozli"
        EVENT = "event", "Hodisa"

    class TranscriptStatus(models.TextChoices):
        NONE = "none", "—"
        OK = "ok", "Aniq"
        LOW_CONFIDENCE = "low_confidence", "Noaniq"
        FAILED = "failed", "Xato"
        REJECTED = "rejected", "Rad etildi"

    class AIStatus(models.TextChoices):
        NONE = "none", "—"
        OK = "ok", "Javob berildi"
        FAILED = "failed", "AI xatosi"
        SKIPPED_HUMAN = "skipped_human", "Operator rejimi"

    class Delivery(models.TextChoices):
        NOT_APPLICABLE = "n/a", "—"
        PENDING = "pending", "Navbatda"
        SENT = "sent", "Yuborildi"
        FAILED = "failed", "Xato"
        DEMO = "demo", "Demo outbox"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="messages")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=16, choices=Sender.choices)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.TEXT)
    text = models.TextField(blank=True)
    language = models.CharField(max_length=2, blank=True)
    external_id = models.CharField(max_length=128, null=True, blank=True)
    transcript_status = models.CharField(max_length=20, choices=TranscriptStatus.choices, default=TranscriptStatus.NONE)
    transcript_confidence = models.FloatField(null=True, blank=True)
    is_demo = models.BooleanField(default=False, help_text="Demo AI javobi yoki demo transkript")
    ai_status = models.CharField(max_length=20, choices=AIStatus.choices, default=AIStatus.NONE)
    sources = models.JSONField(default=list, blank=True)
    tool_trace = models.JSONField(default=list, blank=True)
    delivery_status = models.CharField(max_length=16, choices=Delivery.choices, default=Delivery.NOT_APPLICABLE)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "external_id"],
                condition=Q(external_id__isnull=False),
                name="uniq_message_external_id",
            )
        ]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.sender}: {self.text[:40]}"


def attachment_upload_to(instance, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"org_{instance.organization_id}/attachments/{uuid.uuid4().hex}.{ext}"


class Attachment(models.Model):
    class Kind(models.TextChoices):
        VOICE = "voice", "Ovozli xabar"
        FILE = "file", "Fayl"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.VOICE)
    file = models.FileField(upload_to=attachment_upload_to)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    duration_seconds = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)


class HumanHandoff(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "So'raldi"
        ACTIVE = "active", "Operator suhbatda"
        RETURNED = "returned", "AI'ga qaytarildi"

    class Via(models.TextChoices):
        AI = "ai", "AI"
        CUSTOMER = "customer", "Mijoz"
        OPERATOR = "operator", "Operator"
        SYSTEM = "system", "Tizim"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="handoffs")
    requested_via = models.CharField(max_length=16, choices=Via.choices)
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED)
    taken_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    taken_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    returned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
