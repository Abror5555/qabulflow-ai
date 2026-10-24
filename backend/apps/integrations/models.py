from django.db import models
from django.utils import timezone


class IntegrationStatus(models.Model):
    """Tashqi integratsiyalarning HAQIQIY holati (maxfiy qiymatlarsiz)."""

    class Kind(models.TextChoices):
        TELEGRAM = "telegram", "Telegram bot"
        AI = "ai", "AI provider"
        STT = "stt", "Speech-to-text"

    class State(models.TextChoices):
        NOT_CONFIGURED = "not_configured", "Sozlanmagan"
        DEMO = "demo", "Demo rejim"
        CONFIGURED = "configured", "Sozlangan, tekshirilmagan"
        CONNECTED = "connected", "Ulangan"
        ERROR = "error", "Xato"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="integration_statuses")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    state = models.CharField(max_length=20, choices=State.choices, default=State.NOT_CONFIGURED)
    details = models.JSONField(default=dict, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "kind"], name="uniq_integration_kind")]


class ProcessedTelegramUpdate(models.Model):
    """Bir Telegram update qayta yetkazilsa, takroriy ishlov berilmasligi uchun."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="+")
    update_id = models.BigIntegerField()
    status = models.CharField(max_length=16, default="processing")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "update_id"], name="uniq_tg_update")]
