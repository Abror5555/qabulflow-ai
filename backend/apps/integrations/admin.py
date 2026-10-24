"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin

from apps.integrations.models import IntegrationStatus, ProcessedTelegramUpdate

admin.site.register(IntegrationStatus)
admin.site.register(ProcessedTelegramUpdate)
