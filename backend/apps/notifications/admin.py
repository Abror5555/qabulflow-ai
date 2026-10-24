"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin

from apps.notifications.models import Notification, OutboxMessage, Reminder

for model in (Reminder, Notification, OutboxMessage):
    admin.site.register(model)
