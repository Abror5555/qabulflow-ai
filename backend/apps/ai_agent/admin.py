"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin

from apps.ai_agent.models import AICallLog, AISettings

admin.site.register(AISettings)
admin.site.register(AICallLog)
