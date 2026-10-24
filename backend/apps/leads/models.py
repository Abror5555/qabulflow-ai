from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Lead(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "Yangi"
        QUALIFIED = "qualified", "Ehtiyoj aniqlandi"
        TRIAL_BOOKED = "trial_booked", "Sinovga yozildi"
        TRIAL_ATTENDED = "trial_attended", "Sinovga keldi"
        ENROLLED = "enrolled", "O'qishga yozildi"
        LOST = "lost", "Yo'qotilgan"

    class Source(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        WEBCHAT = "webchat", "Veb-chat"
        MANUAL = "manual", "Qo'lda"
        REFERRAL = "referral", "Tavsiya"
        WALK_IN = "walk_in", "Tashrif"

    STATUS_ORDER = ["new", "qualified", "trial_booked", "trial_attended", "enrolled"]

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="leads")
    branch = models.ForeignKey("organizations.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="leads")
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    phone_verified = models.BooleanField(default=False)
    telegram_user_id = models.BigIntegerField(null=True, blank=True)
    telegram_username = models.CharField(max_length=64, blank=True)
    language = models.CharField(max_length=2, default="uz", choices=settings.LANGUAGES)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    interested_course = models.ForeignKey("courses.Course", null=True, blank=True, on_delete=models.SET_NULL, related_name="interested_leads")
    goal = models.CharField(max_length=255, blank=True)
    level = models.CharField(max_length=64, blank=True)
    preferred_time = models.CharField(max_length=64, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_leads")
    consent_reminders = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    is_test = models.BooleanField(default=False, help_text="AI test-chat uchun yaratilgan; ro'yxat va statistikaga kirmaydi")
    last_activity_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["organization", "created_at"]), models.Index(fields=["organization", "status"])]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "telegram_user_id"],
                condition=Q(telegram_user_id__isnull=False),
                name="uniq_lead_telegram_user_per_org",
            )
        ]

    def __str__(self) -> str:
        return self.full_name or f"Mijoz #{self.pk}"

    @property
    def display_name(self) -> str:
        return self.full_name or f"Mijoz #{self.pk}"


class LeadNote(TimeStampedModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    text = models.TextField()

    class Meta:
        ordering = ["-created_at"]


class LeadStatusChange(models.Model):
    class ChangedVia(models.TextChoices):
        AI = "ai", "AI"
        OPERATOR = "operator", "Xodim"
        SYSTEM = "system", "Tizim"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="status_changes")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    changed_via = models.CharField(max_length=16, choices=ChangedVia.choices, default=ChangedVia.SYSTEM)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["lead", "to_status"])]
