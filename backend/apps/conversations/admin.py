"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin

from apps.conversations.models import Attachment, Conversation, HumanHandoff, Message

for model in (Conversation, Message, Attachment, HumanHandoff):
    admin.site.register(model)
