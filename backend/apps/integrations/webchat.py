"""Veb-chat (vidjet) uchun ochiq API. Tashkilot faqat vidjet public_key orqali, mijoz esa
imzolangan visitor token orqali aniqlanadi. Biznes qoidalari Telegram bilan bir xil (inbound)."""

from __future__ import annotations

import uuid
import zoneinfo
from urllib.parse import urlparse

from django.conf import settings
from django.core import signing
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.ai_agent.services import get_ai_settings
from apps.ai_agent.stt import AudioInput
from apps.ai_agent.texts import t
from apps.conversations import inbound
from apps.conversations.models import Message
from apps.core.exceptions import BusinessError
from apps.core.schema import S, json_view
from apps.organizations.models import WidgetSettings

TOKEN_SALT = "qabulflow.webchat"
TOKEN_MAX_AGE = 60 * 60 * 24 * 30


class WebchatThrottle(AnonRateThrottle):
    scope = "webchat"


class WebchatSessionThrottle(AnonRateThrottle):
    scope = "webchat_session"


class PublicMessageSerializer(serializers.ModelSerializer):
    sender_label = serializers.SerializerMethodField()
    sources = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "sender", "sender_label", "kind", "text", "is_demo", "transcript_status", "sources", "created_at"]

    def get_sender_label(self, obj) -> str:
        return {"customer": "Siz", "ai": "AI yordamchi", "operator": "Administrator", "system": "Tizim"}.get(obj.sender, "")

    def get_sources(self, obj) -> list[dict]:
        # Faqat mijozlar uchun ochiq hujjat nomlari (tool natijasida allaqachon filtrlangan)
        return [{"title": s.get("document_title"), "page": s.get("page")} for s in (obj.sources or [])][:3]


class PublicWidgetMixin:
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [WebchatThrottle]

    def get_widget(self, request, public_key: str) -> WidgetSettings:
        widget = WidgetSettings.objects.select_related("organization").filter(public_key=public_key, is_enabled=True, organization__is_active=True).first()
        if widget is None:
            raise BusinessError("widget_not_found", "Vidjet topilmadi yoki o'chirilgan.", status_code=404)
        origin = request.headers.get("Origin")
        if origin and widget.allowed_origins:
            own = urlparse(settings.PUBLIC_BASE_URL)
            own_origin = f"{own.scheme}://{own.netloc}"
            host_origin = f"{request.scheme}://{request.get_host()}"
            if origin not in widget.allowed_origins and origin not in (own_origin, host_origin):
                raise BusinessError("origin_not_allowed", "Bu sayt uchun vidjetga ruxsat berilmagan.", status_code=403)
        try:
            timezone.activate(zoneinfo.ZoneInfo(widget.organization.timezone))
        except Exception:  # noqa: BLE001
            pass
        return widget

    def get_visitor(self, request, widget) -> str:
        raw = request.headers.get("X-Visitor-Token") or ""
        try:
            data = signing.loads(raw, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        except signing.BadSignature:
            raise BusinessError("invalid_session", "Sessiya muddati tugagan. Sahifani yangilang.", status_code=401) from None
        if data.get("o") != widget.organization_id:
            raise BusinessError("invalid_session", "Sessiya bu vidjetga tegishli emas.", status_code=401)
        return data["v"]


@json_view("Veb-chat vidjet sozlamalari (public)", tags=["webchat"])
class WidgetConfigView(PublicWidgetMixin, APIView):
    def get(self, request, public_key):
        widget = self.get_widget(request, public_key)
        org = widget.organization
        ai = get_ai_settings(org)
        return Response(
            {
                "title": widget.title or org.name,
                "organization_name": org.name,
                "accent_color": widget.accent_color,
                "position": widget.position,
                "languages": ai.enabled_languages,
                "default_language": org.default_language,
                "greetings": {lang: ai.greeting_for(lang, org.name) for lang in ai.enabled_languages},
                "privacy": {lang: t("privacy", lang) for lang in ai.enabled_languages},
                "quick_replies": {
                    lang: [
                        t("btn_trial", lang),
                        t("btn_courses", lang),
                        t("btn_prices", lang),
                        t("btn_branches", lang),
                        t("btn_my_bookings", lang),
                        t("btn_admin", lang),
                    ]
                    for lang in ai.enabled_languages
                },
                "demo_mode": settings.DEMO_MODE,
                "ai_demo": settings.AI_PROVIDER == "demo",
                "voice_enabled": True,
                "audio_max_seconds": settings.AUDIO_MAX_SECONDS,
            }
        )


@json_view("Veb-chat sessiyasi (token) yaratish", {"token": S.CharField(required=False)}, name="WidgetSessionRequest", tags=["webchat"])
class WidgetSessionView(PublicWidgetMixin, APIView):
    throttle_classes = [WebchatSessionThrottle]

    def post(self, request, public_key):
        widget = self.get_widget(request, public_key)
        raw = request.headers.get("X-Visitor-Token")
        if raw:
            try:
                data = signing.loads(raw, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
                if data.get("o") == widget.organization_id:
                    return Response({"token": raw, "visitor_id": data["v"]})
            except signing.BadSignature:
                pass
        visitor_id = f"web_{uuid.uuid4().hex}"
        token = signing.dumps({"o": widget.organization_id, "v": visitor_id}, salt=TOKEN_SALT)
        return Response({"token": token, "visitor_id": visitor_id}, status=status.HTTP_201_CREATED)


@json_view(
    "Veb-chat xabarlari (GET: after_id; POST: yangi xabar)",
    {"text": S.CharField(), "language": S.ChoiceField(choices=["uz", "ru", "en"], required=False), "client_message_id": S.CharField(required=False)},
    name="WidgetMessageRequest",
    tags=["webchat"],
)
class WidgetMessagesView(PublicWidgetMixin, APIView):
    parser_classes = [JSONParser]

    def get(self, request, public_key):
        widget = self.get_widget(request, public_key)
        visitor = self.get_visitor(request, widget)
        conversation = inbound.get_webchat_conversation(widget.organization, visitor_id=visitor, create=False)
        if conversation is None:
            return Response({"conversation": None, "messages": []})
        qs = conversation.messages.exclude(text="").order_by("created_at", "id")
        after = request.query_params.get("after_id")
        if after and after.isdigit():
            qs = qs.filter(id__gt=int(after))
        return Response(
            {
                "conversation": {"id": conversation.id, "mode": conversation.mode, "language": conversation.language},
                "messages": PublicMessageSerializer(qs[:200], many=True).data,
            }
        )

    def post(self, request, public_key):
        widget = self.get_widget(request, public_key)
        visitor = self.get_visitor(request, widget)
        text = str(request.data.get("text", "")).strip()
        if not text:
            raise BusinessError("empty_message", "Xabar bo'sh.", status_code=400)
        if len(text) > 2000:
            raise BusinessError("too_long", "Xabar 2000 belgidan oshmasin.", status_code=400)
        language = request.data.get("language")
        conversation = inbound.get_webchat_conversation(widget.organization, visitor_id=visitor, language=language if language in ("uz", "ru", "en") else None)
        client_id = str(request.data.get("client_message_id", ""))[:64] or None
        result = inbound.process_text(conversation, text, external_id=f"web:{client_id}" if client_id else None)
        return Response(
            {
                "conversation": {"id": result.conversation.id, "mode": result.conversation.mode, "language": result.conversation.language},
                "customer_message": PublicMessageSerializer(result.customer_message).data,
                "replies": PublicMessageSerializer(result.replies, many=True).data,
            },
            status=status.HTTP_201_CREATED if not result.duplicate else status.HTTP_200_OK,
        )


@json_view(
    "Veb-chat ovozli xabari (multipart: audio, language, duration)",
    {"audio": S.FileField(), "language": S.CharField(required=False), "duration": S.FloatField(required=False)},
    name="WidgetVoiceRequest",
    tags=["webchat"],
)
class WidgetVoiceView(PublicWidgetMixin, APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, public_key):
        widget = self.get_widget(request, public_key)
        visitor = self.get_visitor(request, widget)
        upload = request.FILES.get("audio")
        if upload is None:
            raise BusinessError("no_audio", "Audio fayl yuborilmadi.", status_code=400)
        if upload.size > settings.AUDIO_MAX_BYTES:
            raise BusinessError("too_large", f"Audio hajmi {settings.AUDIO_MAX_BYTES // (1024 * 1024)} MB dan oshmasin.", status_code=400)
        language = request.data.get("language")
        conversation = inbound.get_webchat_conversation(widget.organization, visitor_id=visitor, language=language if language in ("uz", "ru", "en") else None)
        duration = request.data.get("duration")
        audio = AudioInput(data=upload.read(), content_type=upload.content_type or "", duration_seconds=None, filename=upload.name)
        try:
            declared = float(duration) if duration else None
        except ValueError:
            declared = None
        if declared and declared > settings.AUDIO_MAX_SECONDS:
            audio.duration_seconds = declared
        result = inbound.process_voice(conversation, audio)
        return Response(
            {
                "conversation": {"id": result.conversation.id, "mode": result.conversation.mode, "language": result.conversation.language},
                "customer_message": PublicMessageSerializer(result.customer_message).data,
                "replies": PublicMessageSerializer(result.replies, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )


@json_view("Veb-chat tilini o'zgartirish", {"language": S.ChoiceField(choices=["uz", "ru", "en"])}, name="WidgetLanguageRequest", tags=["webchat"])
class WidgetLanguageView(PublicWidgetMixin, APIView):
    def post(self, request, public_key):
        widget = self.get_widget(request, public_key)
        visitor = self.get_visitor(request, widget)
        lang = request.data.get("language")
        if lang not in ("uz", "ru", "en"):
            raise BusinessError("invalid_language", "Til: uz, ru yoki en.", status_code=400)
        conversation = inbound.get_webchat_conversation(widget.organization, visitor_id=visitor, create=False)
        if conversation is not None:
            inbound.set_language(conversation, lang)
        return Response({"language": lang})
