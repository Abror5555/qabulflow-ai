"""Kanaldan mustaqil kiruvchi xabar jarayoni (Telegram, veb-chat, AI test-chat).

1) mijoz va suhbatni topish/yaratish  2) xabarni saqlash (dublikatdan himoya)
3) ovozli bo'lsa: tekshiruv + speech-to-text  4) operator rejimida AI javob bermaydi
5) AI agent javobi  6) xato bo'lsa — tushunarli javob, xabar yo'qolmaydi, xodim xabardor.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.ai_agent import nlu
from apps.ai_agent.engine import AgentRunner, BudgetExceeded
from apps.ai_agent.models import AICallLog
from apps.ai_agent.providers.base import AIProviderError
from apps.ai_agent.services import get_ai_settings
from apps.ai_agent.stt import AudioInput, AudioRejected, get_stt_provider, validate_audio
from apps.ai_agent.texts import t
from apps.conversations import services as conv_services
from apps.conversations.models import Attachment, Conversation, Message
from apps.leads import services as lead_services
from apps.leads.models import Lead

logger = logging.getLogger(__name__)


@dataclass
class InboundResult:
    conversation: Conversation
    customer_message: Message
    replies: list[Message] = field(default_factory=list)
    duplicate: bool = False


# --------------------------------------------------------------------------- conversations
def get_telegram_conversation(
    organization, *, chat_id: int, user_id: int, username: str = "", full_name: str = "", language: str | None = None
) -> Conversation:
    lang = language if language in {"uz", "ru", "en"} else organization.default_language
    lead, _ = lead_services.get_or_create_telegram_lead(organization, telegram_user_id=user_id, username=username, full_name="", language=lang)
    conversation, _ = Conversation.objects.get_or_create(
        organization=organization,
        channel=Conversation.Channel.TELEGRAM,
        external_chat_id=str(chat_id),
        defaults={"lead": lead, "language": lead.language or lang},
    )
    return conversation


def get_webchat_conversation(organization, *, visitor_id: str, language: str | None = None, create: bool = True) -> Conversation | None:
    conversation = (
        Conversation.objects.select_related("lead", "organization")
        .filter(organization=organization, channel=Conversation.Channel.WEBCHAT, external_chat_id=visitor_id)
        .first()
    )
    if conversation or not create:
        return conversation
    lang = language if language in {"uz", "ru", "en"} else organization.default_language
    with transaction.atomic():
        lead = lead_services.create_lead(organization, source=Lead.Source.WEBCHAT, language=lang, via="ai")
        conversation, created = Conversation.objects.get_or_create(
            organization=organization,
            channel=Conversation.Channel.WEBCHAT,
            external_chat_id=visitor_id,
            defaults={"lead": lead, "language": lang, "language_locked": bool(language)},
        )
        if not created:
            transaction.set_rollback(True)
    return conversation


def get_test_conversation(organization, user) -> Conversation:
    external = f"staff:{user.id}"
    conversation = Conversation.objects.filter(organization=organization, channel=Conversation.Channel.TEST, external_chat_id=external).first()
    if conversation:
        return conversation
    lead = lead_services.create_lead(organization, source=Lead.Source.MANUAL, full_name="Test mijoz", is_test=True, via="system", notify=False)
    return Conversation.objects.create(
        organization=organization, lead=lead, channel=Conversation.Channel.TEST, external_chat_id=external, language=organization.default_language
    )


def reset_test_conversation(organization, user) -> None:
    Conversation.objects.filter(organization=organization, channel=Conversation.Channel.TEST, external_chat_id=f"staff:{user.id}").delete()
    Lead.objects.filter(organization=organization, is_test=True, conversations__isnull=True).delete()


def set_language(conversation: Conversation, lang: str) -> Conversation:
    if lang not in {"uz", "ru", "en"}:
        return conversation
    conversation.language = lang
    conversation.language_locked = True
    conversation.save(update_fields=["language", "language_locked", "updated_at"])
    lead = conversation.lead
    if lead.language != lang:
        lead.language = lang
        lead.save(update_fields=["language", "updated_at"])
    return conversation


def _maybe_switch_language(conversation: Conversation, text: str) -> None:
    if conversation.language_locked:
        return
    detected = nlu.detect_language(text)
    if detected and detected != conversation.language and len(nlu.words(text)) >= 2:
        ai_settings = get_ai_settings(conversation.organization)
        if detected in (ai_settings.enabled_languages or ["uz", "ru", "en"]):
            conversation.language = detected
            conversation.save(update_fields=["language", "updated_at"])
            Lead.objects.filter(pk=conversation.lead_id).update(language=detected)
            conversation.lead.language = detected


# --------------------------------------------------------------------------- processing
def _reply(conversation: Conversation, text: str, *, is_demo: bool = False, ai_status: str = Message.AIStatus.OK, sources=None, tool_trace=None) -> Message:
    return conv_services.add_outbound_message(
        conversation, sender=Message.Sender.AI, text=text, is_demo=is_demo, ai_status=ai_status, sources=sources, tool_trace=tool_trace
    )


def _notify_ai_error(conversation: Conversation, code: str) -> None:
    from apps.notifications.services import notify_staff

    Conversation.objects.filter(pk=conversation.pk).update(needs_attention=True)
    notify_staff(
        conversation.organization,
        "ai_error",
        "AI javob bera olmadi",
        f"{conversation.lead.display_name}: {code}",
        link=f"/conversations/{conversation.id}",
        min_role="operator",
    )


def run_agent(conversation: Conversation, customer_message: Message, *, now=None, provider=None) -> list[Message]:
    """Suhbat qatorini qulflab (bir suhbatda xabarlar ketma-ket ishlanadi) agentni ishga tushiradi."""

    ai_settings = get_ai_settings(conversation.organization)
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().select_related("lead", "organization").get(pk=conversation.pk)
        if conversation.mode == Conversation.Mode.HUMAN:
            Message.objects.filter(pk=customer_message.pk).update(ai_status=Message.AIStatus.SKIPPED_HUMAN)
            Conversation.objects.filter(pk=conversation.pk).update(needs_attention=True)
            return []
        if not ai_settings.is_enabled:
            conv_services.request_handoff(conversation, via="system", reason="AI o'chirilgan")
            Message.objects.filter(pk=customer_message.pk).update(ai_status=Message.AIStatus.SKIPPED_HUMAN)
            return [_reply(conversation, t("handoff", conversation.language), ai_status=Message.AIStatus.NONE)]

        _maybe_switch_language(conversation, customer_message.text)
        if nlu.has_any(customer_message.text, [k.lower() for k in (ai_settings.handoff_keywords or [])]):
            # Mijoz odam so'rasa — LLM'ga bog'liq bo'lmagan deterministik o'tkazish
            from apps.ai_agent.services import in_working_hours, working_hours_label

            if conversation.channel != "test":
                conv_services.request_handoff(conversation, via="customer", reason="Mijoz administrator so'radi")
            Message.objects.filter(pk=customer_message.pk).update(ai_status=Message.AIStatus.OK)
            text = t("handoff", conversation.language)
            if ai_settings.handoff_outside_hours_notice and not in_working_hours(ai_settings, now):
                text += t("handoff_outside_hours", conversation.language, hours=working_hours_label(ai_settings, conversation.language))
            return [_reply(conversation, text, is_demo=False, ai_status=Message.AIStatus.OK)]

        runner = AgentRunner(conversation, customer_message, now=now, provider=provider)
        try:
            with transaction.atomic():
                reply = runner.respond()
                Conversation.objects.filter(pk=conversation.pk).update(state=runner.executor.state)
        except BudgetExceeded:
            runner.flush_logs()
            Message.objects.filter(pk=customer_message.pk).update(ai_status=Message.AIStatus.FAILED)
            conv_services.request_handoff(conversation, via="system", reason="AI token limiti tugadi")
            return [_reply(conversation, t("budget_exceeded", conversation.language), ai_status=Message.AIStatus.FAILED)]
        except AIProviderError as exc:
            runner.flush_logs()
            Message.objects.filter(pk=customer_message.pk).update(ai_status=Message.AIStatus.FAILED)
            _notify_ai_error(conversation, exc.code)
            return [_reply(conversation, t("ai_error", conversation.language), ai_status=Message.AIStatus.FAILED)]

        Message.objects.filter(pk=customer_message.pk).update(ai_status=Message.AIStatus.OK)
        return [_reply(conversation, reply.text, is_demo=reply.is_demo, sources=reply.sources, tool_trace=reply.tool_trace)]


def process_text(conversation: Conversation, text: str, *, external_id: str | None = None, now=None, provider=None) -> InboundResult:
    text = (text or "").strip()
    language = nlu.detect_language(text) or ""
    recorded = conv_services.record_customer_message(conversation, text=text, external_id=external_id, language=language, created_at=now)
    if recorded.duplicate:
        replies = list(conversation.messages.filter(id__gt=recorded.message.id, sender=Message.Sender.AI)[:1])
        return InboundResult(conversation, recorded.message, replies, duplicate=True)
    if not text:
        return InboundResult(conversation, recorded.message, [])
    replies = run_agent(conversation, recorded.message, now=now, provider=provider)
    conversation.refresh_from_db()
    return InboundResult(conversation, recorded.message, replies)


def process_voice(conversation: Conversation, audio: AudioInput, *, external_id: str | None = None, now=None, stt=None, provider=None) -> InboundResult:
    recorded = conv_services.record_customer_message(conversation, text="", kind=Message.Kind.VOICE, external_id=external_id, created_at=now)
    message = recorded.message
    if recorded.duplicate:
        return InboundResult(conversation, message, [], duplicate=True)
    lang = conversation.language

    try:
        fmt = validate_audio(audio)
    except AudioRejected as exc:
        message.transcript_status = Message.TranscriptStatus.REJECTED
        message.text = "[Ovozli xabar qabul qilinmadi]"
        message.save(update_fields=["transcript_status", "text"])
        key = "voice_bad_format" if exc.code == "bad_format" else "voice_too_long"
        from django.conf import settings as dj_settings

        return InboundResult(
            conversation, message, [_reply(conversation, t(key, lang, seconds=dj_settings.AUDIO_MAX_SECONDS), ai_status=Message.AIStatus.NONE)]
        )

    Attachment.objects.create(
        organization_id=conversation.organization_id,
        message=message,
        kind=Attachment.Kind.VOICE,
        file=ContentFile(audio.data, name=f"{uuid.uuid4().hex}.{fmt}"),
        content_type=audio.content_type or f"audio/{fmt}",
        size_bytes=len(audio.data),
        duration_seconds=audio.duration_seconds,
    )

    try:
        engine = stt or get_stt_provider()
        transcript = engine.transcribe(audio, language_hint=lang)
        AICallLog.objects.create(
            organization=conversation.organization,
            conversation=conversation,
            provider=transcript.provider,
            model=transcript.model,
            kind="stt",
            status=AICallLog.Status.OK,
            latency_ms=transcript.latency_ms,
        )
    except AIProviderError as exc:
        AICallLog.objects.create(
            organization=conversation.organization,
            conversation=conversation,
            provider=getattr(stt, "name", "stt"),
            kind="stt",
            status=AICallLog.Status.ERROR,
            error_code=exc.code[:64],
        )
        message.transcript_status = Message.TranscriptStatus.FAILED
        message.text = "[Ovozli xabar — transkripsiya bajarilmadi]"
        message.save(update_fields=["transcript_status", "text"])
        _notify_ai_error(conversation, f"stt:{exc.code}")
        return InboundResult(conversation, message, [_reply(conversation, t("voice_failed", lang), ai_status=Message.AIStatus.FAILED)])

    from django.conf import settings as dj_settings

    message.text = transcript.text[:4000]
    message.transcript_confidence = transcript.confidence
    message.is_demo = transcript.is_demo
    low = not transcript.text.strip() or (transcript.confidence is not None and transcript.confidence < dj_settings.STT_MIN_CONFIDENCE)
    message.transcript_status = Message.TranscriptStatus.LOW_CONFIDENCE if low else Message.TranscriptStatus.OK
    message.save(update_fields=["text", "transcript_confidence", "is_demo", "transcript_status"])
    conv_services.touch_conversation(conversation, message)

    if low:
        # Noaniq transkripsiya asosida bron yoki boshqa amal bajarilmaydi — aniqlashtirish so'raladi.
        return InboundResult(
            conversation,
            message,
            [_reply(conversation, t("voice_unclear", lang, transcript=transcript.text[:120] or "…"), ai_status=Message.AIStatus.NONE)],
        )
    replies = run_agent(conversation, message, now=now, provider=provider)
    conversation.refresh_from_db()
    return InboundResult(conversation, message, replies)


def greeting_message(conversation: Conversation) -> Message:
    ai_settings = get_ai_settings(conversation.organization)
    lang = conversation.language
    text = ai_settings.greeting_for(lang, conversation.organization.name) + "\n\n" + t("privacy", lang) + "\n\n" + t("menu_hint", lang)
    return conv_services.add_outbound_message(conversation, sender=Message.Sender.AI, text=text, ai_status=Message.AIStatus.NONE, created_at=timezone.now())
