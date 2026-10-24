"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin

from apps.organizations.models import Branch, Membership, Organization, WidgetSettings

for model in (Organization, Branch, Membership, WidgetSettings):
    admin.site.register(model)
