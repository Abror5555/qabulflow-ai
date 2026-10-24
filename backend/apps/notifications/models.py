from django.conf import settings
from django.db import models
from django.utils import timezone


class Reminder(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Rejalashtirilgan"
        SENT = "sent", "Yuborildi"
        CANCELLED = "cancelled", "Bekor qilindi"
        SKIPPED = "skipped", "O'tkazib yuborildi"
        FAILED = "failed", "Xato"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    booking = models.ForeignKey("bookings.TrialBooking", on_delete=models.CASCADE, related_name="reminders")
    scheduled_for = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["scheduled_for"]
        constraints = [models.UniqueConstraint(fields=["booking"], condition=models.Q(status="scheduled"), name="uniq_scheduled_reminder_per_booking")]


class Notification(models.Model):
    """Panel ichidagi bildirishnomalar (qo'ng'iroqcha)."""

    class Kind(models.TextChoices):
        NEW_BOOKING = "new_booking", "Yangi bron"
        BOOKING_CANCELLED = "booking_cancelled", "Bron bekor qilindi"
        HANDOFF_REQUESTED = "handoff_requested", "Operator so'raldi"
        AI_ERROR = "ai_error", "AI xatosi"
        NEW_LEAD = "new_lead", "Yangi mijoz"
        SYSTEM = "system", "Tizim"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="notifications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=500, blank=True)
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class OutboxMessage(models.Model):
    """Tashqi kanallarga yuboriladigan xabarlar navbati.

    dedup_key orqali takroriy jo'natishdan himoya qilinadi. DEMO_MODE yoki token
    yo'q bo'lsa, xabar hech kimga yuborilmaydi — status=demo bo'lib, panelda
    "Demo outbox" ichida ko'rinadi.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Navbatda"
        SENDING = "sending", "Yuborilmoqda"
        SENT = "sent", "Yuborildi"
        FAILED = "failed", "Xato"
        DEMO = "demo", "Demo outbox"

    class Kind(models.TextChoices):
        REPLY = "reply", "Javob"
        REMINDER = "reminder", "Eslatma"
        SYSTEM = "system", "Tizim"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="outbox")
    channel = models.CharField(max_length=16)
    recipient = models.CharField(max_length=128)
    text = models.TextField()
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.REPLY)
    message = models.ForeignKey("conversations.Message", null=True, blank=True, on_delete=models.SET_NULL, related_name="outbox_items")
    dedup_key = models.CharField(max_length=128, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=255, blank=True)
    external_message_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
