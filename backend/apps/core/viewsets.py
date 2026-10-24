"""Tashkilot chegarasida ishlaydigan umumiy viewset mixinlari."""

from __future__ import annotations

from django.db.models import Q, QuerySet


def branch_scope_q(membership, field: str) -> Q | None:
    """A'zolik muayyan filiallarga cheklangan bo'lsa, filtr qaytaradi.

    Cheklov bo'lmasa (bo'sh ro'yxat) — None. Filial biriktirilmagan yozuvlar
    (masalan, hali filial aniqlanmagan yangi lead) hammaga ko'rinadi.
    """
    if membership is None or membership.role == "owner":
        return None
    branch_ids = list(membership.branches.values_list("id", flat=True))
    if not branch_ids:
        return None
    return Q(**{f"{field}__in": branch_ids}) | Q(**{f"{field}__isnull": True})


class OrganizationScopedMixin:
    """get_queryset'ni har doim request.organization bilan cheklaydi.

    organization_field — modeldagi tashkilot maydoniga yo'l.
    branch_field — filial cheklovi uchun yo'l (ixtiyoriy).
    """

    organization_field = "organization"
    branch_field: str | None = None

    def scope_queryset(self, qs: QuerySet) -> QuerySet:
        qs = qs.filter(**{self.organization_field: self.request.organization})
        if self.branch_field:
            q = branch_scope_q(self.request.membership, self.branch_field)
            if q is not None:
                qs = qs.filter(q)
        return qs

    def get_queryset(self):
        return self.scope_queryset(super().get_queryset())

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["organization"] = getattr(self.request, "organization", None)
        ctx["membership"] = getattr(self.request, "membership", None)
        return ctx
