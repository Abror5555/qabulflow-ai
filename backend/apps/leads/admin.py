"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin

from apps.leads.models import Lead, LeadNote, LeadStatusChange


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ["id", "full_name", "organization", "source", "status", "created_at"]
    list_filter = ["organization", "status", "source"]
    search_fields = ["full_name", "phone"]


admin.site.register(LeadNote)
admin.site.register(LeadStatusChange)
