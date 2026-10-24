"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin

from apps.core.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "organization", "action", "summary"]
    list_filter = ["organization", "action"]
