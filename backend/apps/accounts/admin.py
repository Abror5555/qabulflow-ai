"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "full_name", "is_active", "is_demo", "is_staff"]
    search_fields = ["email", "full_name"]
    fieldsets = ((None, {"fields": ("email", "password", "full_name")}), ("Holat", {"fields": ("is_active", "is_staff", "is_superuser", "is_demo")}))
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),)
