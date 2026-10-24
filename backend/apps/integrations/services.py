"""Integratsiyalarning HAQIQIY holatini hisoblash. Kalit yo'q bo'lsa — "ulangan" deb ko'rsatilmaydi."""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from apps.ai_agent.models import AICallLog
from apps.core.logging import redact
from apps.integrations.models import IntegrationStatus


def _row(org, kind) -> IntegrationStatus:
    obj, _ = IntegrationStatus.objects.get_or_create(organization=org, kind=kind)
    return obj


def telegram_status(org) -> dict:
    row = _row(org, IntegrationStatus.Kind.TELEGRAM)
    token = bool(settings.TELEGRAM_BOT_TOKEN)
    bound = settings.TELEGRAM_ORGANIZATION_SLUG == org.slug
    if not token:
        state, note = "not_configured", "TELEGRAM_BOT_TOKEN kiritilmagan. Bot ishlamaydi; xabarlar faqat demo outbox'da ko'rinadi."
    elif not bound:
        state, note = "not_configured", f"Bot boshqa tashkilotga biriktirilgan (TELEGRAM_ORGANIZATION_SLUG={settings.TELEGRAM_ORGANIZATION_SLUG})."
    elif settings.DEMO_MODE:
        state, note = "demo", "Token bor, lekin DEMO_MODE yoqilgan — real foydalanuvchilarga xabar yuborilmaydi."
    elif row.state in ("connected", "error") and row.last_checked_at:
        state, note = row.state, row.last_error or "getMe tekshiruvi muvaffaqiyatli."
    else:
        state, note = "configured", 'Token kiritilgan, lekin ulanish hali tekshirilmagan. "Tekshirish" tugmasini bosing.'
    return {
        "kind": "telegram",
        "state": state,
        "note": note,
        "mode": settings.TELEGRAM_MODE,
        "token_configured": token,
        "bound_to_this_org": bound,
        "bot_username": (row.details or {}).get("username"),
        "last_checked_at": row.last_checked_at,
        "last_error": row.last_error,
        "webhook_secret_configured": bool(settings.TELEGRAM_WEBHOOK_SECRET),
    }


def _last_call(org, kind: str):
    qs = AICallLog.objects.filter(organization=org, kind=kind).exclude(provider="demo")
    return qs.order_by("-created_at").values("status", "error_code", "created_at", "provider", "model").first()


def ai_status(org) -> dict:
    row = _row(org, IntegrationStatus.Kind.AI)
    provider = settings.AI_PROVIDER
    if provider == "demo":
        return {
            "kind": "ai",
            "state": "demo",
            "provider": "demo",
            "model": "deterministic-demo",
            "note": "Kalitsiz deterministik demo dialoglar. Bu haqiqiy LLM emas.",
            "last_checked_at": row.last_checked_at,
            "last_error": "",
        }
    key = settings.ANTHROPIC_API_KEY if provider == "anthropic" else settings.OPENAI_API_KEY
    if not key or not settings.AI_MODEL:
        missing = [n for n, v in ((f"{provider.upper()}_API_KEY", key), ("AI_MODEL", settings.AI_MODEL)) if not v]
        return {
            "kind": "ai",
            "state": "not_configured",
            "provider": provider,
            "model": settings.AI_MODEL,
            "note": f"Kiritilmagan: {', '.join(missing)}. Mijozlarga AI javob bermaydi va administrator xabardor qilinadi.",
            "last_checked_at": row.last_checked_at,
            "last_error": "",
        }
    last = _last_call(org, "chat")
    if row.last_checked_at and (not last or row.last_checked_at >= last["created_at"]):
        state, note = row.state, row.last_error or "Model va kalit tekshirildi."
    elif last:
        state = "connected" if last["status"] == "ok" else "error"
        note = "Oxirgi so'rov muvaffaqiyatli." if state == "connected" else f"Oxirgi so'rov xatosi: {last['error_code']}"
    else:
        state, note = "configured", "Kalit va model kiritilgan, hali tekshirilmagan."
    return {
        "kind": "ai",
        "state": state,
        "provider": provider,
        "model": settings.AI_MODEL,
        "note": note,
        "last_checked_at": row.last_checked_at,
        "last_error": row.last_error,
    }


def stt_status(org) -> dict:
    provider = settings.STT_PROVIDER
    if provider == "demo":
        return {
            "kind": "stt",
            "state": "demo",
            "provider": "demo",
            "model": "",
            "note": "Demo transkript: ovozli xabar uchun belgilangan namunaviy matn qaytariladi (haqiqiy speech-to-text emas).",
        }
    if not settings.OPENAI_API_KEY or not settings.STT_MODEL:
        return {
            "kind": "stt",
            "state": "not_configured",
            "provider": provider,
            "model": settings.STT_MODEL,
            "note": "OPENAI_API_KEY yoki STT_MODEL kiritilmagan. Ovozli xabarga matn yuborish taklif qilinadi.",
        }
    last = _last_call(org, "stt")
    if last:
        state = "connected" if last["status"] == "ok" else "error"
        note = "Oxirgi transkripsiya muvaffaqiyatli." if state == "connected" else f"Oxirgi xato: {last['error_code']}"
    else:
        state, note = "configured", "Kalit va model kiritilgan, hali ishlatilmagan."
    return {"kind": "stt", "state": state, "provider": provider, "model": settings.STT_MODEL, "note": note}


def overview(org) -> dict:
    return {"demo_mode": settings.DEMO_MODE, "items": [telegram_status(org), ai_status(org), stt_status(org)]}


def check_telegram(org) -> dict:
    row = _row(org, IntegrationStatus.Kind.TELEGRAM)
    if not settings.TELEGRAM_BOT_TOKEN:
        row.state, row.last_error = "not_configured", "Token kiritilmagan"
    else:
        try:
            from apps.integrations.telegram.sender import get_bot_info

            info = get_bot_info()
            row.state, row.last_error, row.details = "connected", "", info
        except Exception as exc:  # noqa: BLE001
            row.state, row.last_error = "error", redact(f"{exc.__class__.__name__}: {exc}")[:255]
    row.last_checked_at = timezone.now()
    row.save()
    return telegram_status(org)


def check_ai(org) -> dict:
    """Kalit va model mavjudligini models.retrieve orqali tekshiradi (token sarflamaydi)."""

    row = _row(org, IntegrationStatus.Kind.AI)
    provider = settings.AI_PROVIDER
    if provider == "demo":
        row.state, row.last_error = "demo", ""
    else:
        key = settings.ANTHROPIC_API_KEY if provider == "anthropic" else settings.OPENAI_API_KEY
        if not key or not settings.AI_MODEL:
            row.state, row.last_error = "not_configured", "Kalit yoki model kiritilmagan"
        else:
            try:
                if provider == "anthropic":
                    import anthropic

                    anthropic.Anthropic(api_key=key, timeout=15, max_retries=0).models.retrieve(settings.AI_MODEL)
                else:
                    import openai

                    openai.OpenAI(api_key=key, timeout=15, max_retries=0).models.retrieve(settings.AI_MODEL)
                row.state, row.last_error = "connected", ""
            except Exception as exc:  # noqa: BLE001
                row.state, row.last_error = "error", redact(f"{exc.__class__.__name__}")[:255]
    row.last_checked_at = timezone.now()
    row.save()
    return ai_status(org)
