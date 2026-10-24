"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin

from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument

admin.site.register(KnowledgeDocument)
admin.site.register(KnowledgeChunk)
