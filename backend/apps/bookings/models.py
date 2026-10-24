from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel


class TrialBooking(TimeStampedModel):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Tasdiqlangan"
        CANCELLED = "cancelled", "Bekor qilingan"
        ATTENDED = "attended", "Qatnashdi"
        NO_SHOW = "no_show", "Kelmadi"

    class Channel(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        WEBCHAT = "webchat", "Veb-chat"
        PANEL = "panel", "Panel"

    ACTIVE_STATUSES = (Status.CONFIRMED, Status.ATTENDED, Status.NO_SHOW)

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="trial_bookings")
    lead = models.ForeignKey("leads.Lead", on_delete=models.PROTECT, related_name="trial_bookings")
    slot = models.ForeignKey("courses.TrialSlot", on_delete=models.PROTECT, related_name="bookings")
    conversation = models.ForeignKey("conversations.Conversation", null=True, blank=True, on_delete=models.SET_NULL, related_name="bookings")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED, db_index=True)
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.PANEL)
    idempotency_key = models.CharField(max_length=128, null=True, blank=True)
    confirmed_at = models.DateTimeField(default=timezone.now, db_index=True, help_text="Birinchi tasdiqlangan vaqt (o'zgarmaydi)")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    attendance_marked_at = models.DateTimeField(null=True, blank=True)
    reschedule_count = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-confirmed_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="uniq_booking_idempotency_key",
            ),
            models.UniqueConstraint(
                fields=["slot", "lead"],
                condition=~Q(status="cancelled"),
                name="uniq_active_booking_per_lead_slot",
            ),
        ]
        indexes = [models.Index(fields=["organization", "confirmed_at"])]

    def __str__(self) -> str:  # pragma: no cover
        return f"Booking #{self.pk} {self.status}"


class BookingEvent(models.Model):
    class Type(models.TextChoices):
        CONFIRMED = "confirmed", "Tasdiqlandi"
        CANCELLED = "cancelled", "Bekor qilindi"
        RESCHEDULED = "rescheduled", "Ko'chirildi"
        ATTENDED = "attended", "Qatnashdi"
        NO_SHOW = "no_show", "Kelmadi"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    booking = models.ForeignKey(TrialBooking, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=16, choices=Type.choices, db_index=True)
    from_slot = models.ForeignKey("courses.TrialSlot", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    to_slot = models.ForeignKey("courses.TrialSlot", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_type = models.CharField(max_length=16, default="system")
    reason = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["occurred_at", "id"]


class Enrollment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Tasdiq kutilmoqda"
        CONFIRMED = "confirmed", "O'qishga yozildi"
        CANCELLED = "cancelled", "Bekor qilingan"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="enrollments")
    lead = models.ForeignKey("leads.Lead", on_delete=models.PROTECT, related_name="enrollments")
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="enrollments")
    group = models.ForeignKey("courses.Group", null=True, blank=True, on_delete=models.SET_NULL, related_name="enrollments")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    confirmed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["lead", "course"], condition=~Q(status="cancelled"), name="uniq_active_enrollment")]
