import secrets
import zoneinfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel


def validate_timezone(value: str) -> None:
    try:
        zoneinfo.ZoneInfo(value)
    except Exception as exc:  # noqa: BLE001
        raise ValidationError("Noto'g'ri vaqt zonasi") from exc


class Organization(TimeStampedModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=80, unique=True)
    timezone = models.CharField(max_length=64, default="Asia/Tashkent", validators=[validate_timezone])
    default_language = models.CharField(max_length=2, default="uz", choices=settings.LANGUAGES)
    currency = models.CharField(max_length=3, default="UZS")
    is_active = models.BooleanField(default=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Branch(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="uniq_branch_name_per_org")]

    def __str__(self) -> str:
        return self.name


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Egasi"
        MANAGER = "manager", "Menejer"
        OPERATOR = "operator", "Operator"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.OPERATOR)
    branches = models.ManyToManyField(Branch, blank=True, related_name="memberships", help_text="Bo'sh — barcha filiallar")
    is_active = models.BooleanField(default=True)
    notification_prefs = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["organization", "user__full_name"]
        constraints = [models.UniqueConstraint(fields=["user", "organization"], name="uniq_membership")]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"

    DEFAULT_NOTIFICATION_PREFS = {
        "new_booking": True,
        "booking_cancelled": True,
        "handoff_requested": True,
        "ai_error": True,
        "new_lead": False,
    }

    def get_notification_prefs(self) -> dict:
        prefs = dict(self.DEFAULT_NOTIFICATION_PREFS)
        prefs.update({k: bool(v) for k, v in (self.notification_prefs or {}).items() if k in prefs})
        return prefs


def generate_public_key() -> str:
    return "wk_" + secrets.token_urlsafe(18)


class WidgetSettings(TimeStampedModel):
    """Saytga qo'shiladigan veb-chat vidjeti sozlamalari."""

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="widget")
    public_key = models.CharField(max_length=64, unique=True, default=generate_public_key)
    is_enabled = models.BooleanField(default=True)
    allowed_origins = models.JSONField(default=list, blank=True, help_text="Vidjet joylashtirilishi mumkin bo'lgan saytlar")
    title = models.CharField(max_length=80, default="QabulFlow AI")
    accent_color = models.CharField(max_length=7, default="#4F46E5")
    position = models.CharField(max_length=8, choices=[("right", "O'ng"), ("left", "Chap")], default="right")

    def __str__(self) -> str:  # pragma: no cover
        return f"Widget {self.organization}"
