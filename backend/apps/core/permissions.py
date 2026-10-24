"""Rollar: owner > manager > operator. Har bir endpoint va obyekt serverda tekshiriladi."""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

ROLE_LEVEL = {"operator": 1, "manager": 2, "owner": 3}


def role_at_least(request, role: str) -> bool:
    membership = getattr(request, "membership", None)
    if membership is None:
        return False
    return ROLE_LEVEL.get(membership.role, 0) >= ROLE_LEVEL[role]


class IsOrganizationMember(BasePermission):
    message = "Tizimga kiring yoki tashkilotga a'zo bo'ling."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and getattr(request, "membership", None))

    def has_object_permission(self, request, view, obj) -> bool:
        org_id = getattr(obj, "organization_id", None)
        if org_id is None:
            return True
        return org_id == request.organization.id


class _RoleWritePermission(IsOrganizationMember):
    min_write_role = "manager"
    min_read_role = "operator"

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return role_at_least(request, self.min_read_role)
        return role_at_least(request, self.min_write_role)


class ManagerWriteOperatorRead(_RoleWritePermission):
    message = "Bu amal uchun menejer yoki egasi roli kerak."
    min_write_role = "manager"


class OwnerWriteManagerRead(_RoleWritePermission):
    message = "Bu amal faqat tashkilot egasiga ruxsat etilgan."
    min_write_role = "owner"
    min_read_role = "manager"


class OwnerWriteOperatorRead(_RoleWritePermission):
    message = "Bu amal faqat tashkilot egasiga ruxsat etilgan."
    min_write_role = "owner"
    min_read_role = "operator"


class ManagerOnly(IsOrganizationMember):
    message = "Bu bo'lim menejer yoki egasi uchun."

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and role_at_least(request, "manager")


class OwnerOnly(IsOrganizationMember):
    message = "Bu bo'lim faqat tashkilot egasi uchun."

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and role_at_least(request, "owner")
