"""So'rov identifikatori va tashkilot (tenant) kontekstini aniqlovchi middleware.

Tashkilot va rol hech qachon frontend yuborgan ID'dan olinmaydi: foydalanuvchi
autentifikatsiyasi va uning faol a'zoligi (Membership) asosida serverda aniqlanadi.
"""

from __future__ import annotations

import uuid
import zoneinfo

from django.utils import timezone

from apps.core.logging import set_request_id

SESSION_ORG_KEY = "active_org_id"


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        rid = "".join(ch for ch in rid if ch.isalnum() or ch in "-_")[:32]
        request.request_id = rid
        set_request_id(rid)
        response = self.get_response(request)
        response["X-Request-ID"] = rid
        set_request_id("-")
        return response


def resolve_membership(request):
    from apps.organizations.models import Membership

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None
    qs = Membership.objects.select_related("organization").filter(user=user, is_active=True, organization__is_active=True)
    org_id = request.session.get(SESSION_ORG_KEY) if hasattr(request, "session") else None
    membership = None
    if org_id:
        membership = qs.filter(organization_id=org_id).first()
    if membership is None:
        membership = qs.order_by("created_at", "id").first()
        if membership is not None and hasattr(request, "session"):
            request.session[SESSION_ORG_KEY] = membership.organization_id
    return membership


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = None
        request.organization = None
        membership = resolve_membership(request)
        if membership is not None:
            request.membership = membership
            request.organization = membership.organization
            try:
                timezone.activate(zoneinfo.ZoneInfo(membership.organization.timezone))
            except Exception:  # noqa: BLE001
                timezone.activate(zoneinfo.ZoneInfo("Asia/Tashkent"))
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
