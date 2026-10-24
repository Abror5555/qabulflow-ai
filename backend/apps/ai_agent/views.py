from datetime import timedelta

from django.conf import settings
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai_agent.models import AICallLog, AISettings
from apps.ai_agent.services import get_ai_settings
from apps.conversations import inbound
from apps.conversations.serializers import MessageSerializer
from apps.core.audit import record_audit
from apps.core.permissions import ManagerOnly, ManagerWriteOperatorRead
from apps.core.schema import S, json_view

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class WorkingHoursSerializer(serializers.Serializer):
    start = serializers.RegexField(HHMM)
    end = serializers.RegexField(HHMM)
    days = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=6), allow_empty=False)

    def validate(self, attrs):
        if attrs["end"] <= attrs["start"]:
            raise serializers.ValidationError({"end": "Tugash vaqti boshlanishdan keyin bo'lishi kerak."})
        attrs["days"] = sorted(set(attrs["days"]))
        return attrs


class AISettingsSerializer(serializers.ModelSerializer):
    working_hours = WorkingHoursSerializer()
    provider = serializers.SerializerMethodField()

    class Meta:
        model = AISettings
        fields = [
            "is_enabled",
            "greetings",
            "enabled_languages",
            "tone",
            "working_hours",
            "handoff_keywords",
            "handoff_after_failed_attempts",
            "handoff_outside_hours_notice",
            "ask_phone_before_booking",
            "max_slots_to_offer",
            "reminder_hours_before",
            "provider",
            "updated_at",
        ]
        read_only_fields = ["provider", "updated_at"]

    def get_provider(self, obj) -> dict:
        return {
            "name": settings.AI_PROVIDER,
            "model": settings.AI_MODEL if settings.AI_PROVIDER != "demo" else "deterministic-demo",
            "is_demo": settings.AI_PROVIDER == "demo",
        }

    def validate_greetings(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Noto'g'ri format.")
        cleaned = {}
        for lang in ("uz", "ru", "en"):
            text = str(value.get(lang, "")).strip()
            if len(text) > 600:
                raise serializers.ValidationError(f"{lang}: salomlashuv 600 belgidan oshmasin.")
            if text:
                cleaned[lang] = text
        if "uz" not in cleaned:
            raise serializers.ValidationError("O'zbekcha salomlashuv majburiy.")
        return cleaned

    def validate_enabled_languages(self, value):
        langs = [lang for lang in value if lang in ("uz", "ru", "en")]
        if "uz" not in langs:
            raise serializers.ValidationError("O'zbek tili doim yoqilgan bo'lishi kerak (standart til).")
        return list(dict.fromkeys(langs))

    def validate_handoff_keywords(self, value):
        words = [str(v).strip().lower()[:40] for v in value if str(v).strip()]
        if not words:
            raise serializers.ValidationError("Kamida bitta kalit so'z kerak.")
        return list(dict.fromkeys(words))[:30]

    def update(self, instance, validated_data):
        wh = validated_data.pop("working_hours", None)
        if wh is not None:
            instance.working_hours = wh
        return super().update(instance, validated_data)


class AISettingsView(APIView):
    permission_classes = [ManagerWriteOperatorRead]

    @extend_schema(responses=AISettingsSerializer)
    def get(self, request):
        return Response(AISettingsSerializer(get_ai_settings(request.organization)).data)

    @extend_schema(request=AISettingsSerializer, responses=AISettingsSerializer)
    def put(self, request):
        obj = get_ai_settings(request.organization)
        ser = AISettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        record_audit(request.organization, "ai_settings.updated", actor=request.user, obj=obj, summary="AI sozlamalari yangilandi")
        return Response(ser.data)

    patch = put


class TestChatSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000)
    language = serializers.ChoiceField(choices=["uz", "ru", "en"], required=False)


@json_view("AI test-chat (dry-run: bron yaratilmaydi)", {"text": S.CharField(), "language": S.CharField(required=False)}, name="TestChatRequest")
class TestChatView(APIView):
    """AI sozlamalari sahifasidagi test-chat: haqiqiy bron yaratmaydi (dry-run), statistikaga kirmaydi."""

    permission_classes = [ManagerWriteOperatorRead]

    def _messages(self, conversation):
        return MessageSerializer(conversation.messages.order_by("created_at", "id")[:200], many=True).data

    def get(self, request):
        conversation = inbound.get_test_conversation(request.organization, request.user)
        return Response({"conversation_id": conversation.id, "language": conversation.language, "messages": self._messages(conversation)})

    @extend_schema(request=TestChatSerializer)
    def post(self, request):
        ser = TestChatSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        conversation = inbound.get_test_conversation(request.organization, request.user)
        if ser.validated_data.get("language"):
            inbound.set_language(conversation, ser.validated_data["language"])
        result = inbound.process_text(conversation, ser.validated_data["text"])
        return Response(
            {
                "conversation_id": conversation.id,
                "customer_message": MessageSerializer(result.customer_message).data,
                "replies": MessageSerializer(result.replies, many=True).data,
            }
        )

    def delete(self, request):
        inbound.reset_test_conversation(request.organization, request.user)
        return Response({"ok": True})


@json_view("AI chaqiruvlari statistikasi")
class AIUsageView(APIView):
    permission_classes = [ManagerOnly]

    def get(self, request):
        since = timezone.now() - timedelta(days=7)
        qs = AICallLog.objects.filter(organization=request.organization, created_at__gte=since)
        by_status = dict(qs.order_by().values_list("status").annotate(c=Count("id")))
        agg = qs.aggregate(i=Sum("input_tokens"), o=Sum("output_tokens"), lat=Avg("latency_ms"))
        last_error = qs.exclude(status="ok").order_by("-created_at").values("provider", "error_code", "created_at").first()
        return Response(
            {
                "period_days": 7,
                "calls": qs.count(),
                "by_status": by_status,
                "input_tokens": agg["i"] or 0,
                "output_tokens": agg["o"] or 0,
                "avg_latency_ms": round(agg["lat"] or 0),
                "last_error": last_error,
            }
        )
