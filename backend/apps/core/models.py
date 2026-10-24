from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """created_at/updated_at maydonlari. created_at seed uchun aniq berilishi mumkin."""

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditEvent(models.Model):
    """Tizimdagi muhim amallar jurnali (dashboard'dagi "oxirgi harakatlar" ham shundan)."""

    class ActorType(models.TextChoices):
        USER = "user", "Xodim"
        AI = "ai", "AI agent"
        CUSTOMER = "customer", "Mijoz"
        SYSTEM = "system", "Tizim"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_type = models.CharField(max_length=16, choices=ActorType.choices, default=ActorType.SYSTEM)
    action = models.CharField(max_length=64, db_index=True)
    object_type = models.CharField(max_length=64, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["organization", "-created_at"])]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.action} {self.object_type}#{self.object_id}"
