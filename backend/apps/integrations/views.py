import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound, JsonResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.audit import record_audit
from apps.core.permissions import OwnerOnly, OwnerWriteManagerRead
from apps.core.schema import json_view
from apps.integrations import services

logger = logging.getLogger(__name__)


@json_view("Integratsiyalar holati (Telegram, AI, STT, demo rejimi)")
class IntegrationStatusView(APIView):
    permission_classes = [OwnerWriteManagerRead]

    def get(self, request):
        return Response(services.overview(request.organization))


@json_view("Telegram tokenini tekshirish (getMe)", {}, name="TelegramCheckRequest")
class TelegramCheckView(APIView):
    permission_classes = [OwnerOnly]

    def post(self, request):
        result = services.check_telegram(request.organization)
        record_audit(request.organization, "integration.telegram_checked", actor=request.user, summary=f"Telegram tekshiruvi: {result['state']}")
        return Response(result)


@json_view("AI provayder kalit/modelini tekshirish", {}, name="AICheckRequest")
class AICheckView(APIView):
    permission_classes = [OwnerOnly]

    def post(self, request):
        result = services.check_ai(request.organization)
        record_audit(request.organization, "integration.ai_checked", actor=request.user, summary=f"AI tekshiruvi: {result['state']}")
        return Response(result)


@csrf_exempt
@require_POST
def telegram_webhook(request, path_token: str):
    """Himoyalangan webhook: maxfiy yo'l + X-Telegram-Bot-Api-Secret-Token sarlavhasi.

    Faqat TELEGRAM_MODE=webhook bo'lganda ishlaydi (polling bilan bir vaqtda ishlatilmaydi).
    """

    if settings.TELEGRAM_MODE != "webhook" or not settings.TELEGRAM_BOT_TOKEN or settings.DEMO_MODE:
        return HttpResponseNotFound()
    if not settings.TELEGRAM_WEBHOOK_PATH_TOKEN or not constant_time_compare(path_token, settings.TELEGRAM_WEBHOOK_PATH_TOKEN):
        return HttpResponseNotFound()
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not settings.TELEGRAM_WEBHOOK_SECRET or not constant_time_compare(secret, settings.TELEGRAM_WEBHOOK_SECRET):
        return HttpResponseForbidden()
    if len(request.body) > 1024 * 1024:
        return HttpResponse(status=413)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponse(status=400)
    try:
        from apps.integrations.telegram.bot import process_webhook_payload

        process_webhook_payload(payload)
    except Exception:  # noqa: BLE001
        logger.exception("Webhook update ishlovida xato")
        return HttpResponse(status=500)
    return JsonResponse({"ok": True})
