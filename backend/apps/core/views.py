import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def health(request):
    checks = {}
    ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "error"
        ok = False
    try:
        cache.set("healthcheck", "1", 5)
        checks["cache"] = "ok" if cache.get("healthcheck") == "1" else "error"
    except Exception:  # noqa: BLE001
        checks["cache"] = "error"
        ok = False
    checks["demo_mode"] = settings.DEMO_MODE
    return JsonResponse({"status": "ok" if ok else "degraded", "checks": checks}, status=200 if ok else 503)


def spa_index(request, *args, **kwargs):
    """React SPA'ni beradi. /chat/<key> sahifasi vidjet sozlamalariga ko'ra iframe'ga ruxsat oladi."""

    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return HttpResponse(
            "<h1>Frontend build topilmadi</h1><p><code>cd frontend && npm ci && npm run build</code> buyrug'ini bajaring "
            "yoki development uchun <code>npm run dev</code> (http://localhost:5173) dan foydalaning.</p>",
            status=503,
        )
    response = FileResponse(open(index, "rb"), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    path = request.path
    if path.startswith("/chat/"):
        from apps.organizations.models import WidgetSettings

        parts = path.strip("/").split("/")
        key = parts[1] if len(parts) > 1 else ""
        widget = WidgetSettings.objects.filter(public_key=key, is_enabled=True).first()
        if widget is None:
            raise Http404()
        origins = " ".join(o for o in (widget.allowed_origins or []) if o.startswith(("http://", "https://")))
        response["Content-Security-Policy"] = f"frame-ancestors 'self' {origins}".strip()
        response.xframe_options_exempt = True
    return response


@require_GET
def widget_js(request):
    path = settings.BASE_DIR / "static" / "widget.js"
    if not path.exists():
        raise Http404()
    response = FileResponse(open(path, "rb"), content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "public, max-age=300"
    return response


def demo_site(request):
    """Vidjet qanday joylashishini ko'rsatuvchi sintetik "markaz sayti" (faqat DEMO_MODE)."""

    from django.shortcuts import render

    from apps.organizations.models import WidgetSettings

    if not settings.DEMO_MODE:
        raise Http404()
    widget = (
        WidgetSettings.objects.select_related("organization").filter(organization__slug=settings.TELEGRAM_ORGANIZATION_SLUG, is_enabled=True).first()
        or WidgetSettings.objects.select_related("organization").filter(organization__is_demo=True, is_enabled=True).first()
    )
    if widget is None:
        raise Http404()
    return render(request, "demo_site.html", {"widget": widget, "org": widget.organization})
