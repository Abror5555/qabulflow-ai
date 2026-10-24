"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin

from apps.courses.models import Course, Group, TrialSlot

for model in (Course, Group, TrialSlot):
    admin.site.register(model)
