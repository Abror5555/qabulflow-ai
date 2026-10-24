"""Telegram update'larini qayta ishlovchi SINXRON yadro.

aiogram polling handleri ham, webhook Django view'i ham shu bitta klassdan foydalanadi.
Natija — yuboriladigan amallar ro'yxati (OutgoingAction); tarmoq bilan ishlash alohida.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, close_old_connections, connection, transaction

from apps.ai_agent.stt import AudioInput
from apps.ai_agent.texts import t
from apps.conversations import inbound
from apps.conversations.models import Message
from apps.integrations.models import ProcessedTelegramUpdate
from apps.organizations.models import Organization

logger = logging.getLogger(__name__)

LANGUAGE_BUTTON_TEXTS = {t("btn_language", lang) for lang in ("uz", "ru", "en")}


@dataclass
class OutgoingAction:
    chat_id: int
    text: str = ""
    keyboard: str | None = None  # "main" | "language" | None
    lang: str = "uz"
    message_id: int | None = None  # bizning Message.id — yetkazish holatini yangilash uchun
    callback_query_id: str | None = None


def get_bot_organization() -> Organization:
    return Organization.objects.get(slug=settings.TELEGRAM_ORGANIZATION_SLUG, is_active=True)


def map_language(code: str | None) -> str:
    code = (code or "").lower()
    if code.startswith("ru"):
        return "ru"
    if code.startswith("en"):
        return "en"
    return "uz"


class TelegramProcessor:
    def __init__(self, organization: Organization | None = None):
        self.organization = organization or get_bot_organization()

    def _claim(self, update_id: int) -> bool:
        try:
            with transaction.atomic():
                ProcessedTelegramUpdate.objects.create(organization=self.organization, update_id=update_id)
            return True
        except IntegrityError:
            return False

    @staticmethod
    def _refresh_connections() -> None:
        # Uzoq ishlaydigan bot jarayonida eskirgan DB ulanishlarini yopish (tranzaksiya ichida emas)
        if not connection.in_atomic_block:
            close_old_connections()

    def process(self, update, *, voice: AudioInput | None = None, voice_error: str | None = None) -> list[OutgoingAction]:
        self._refresh_connections()
        if not self._claim(update.update_id):
            logger.info("Telegram update %s takroriy — o'tkazib yuborildi", update.update_id)
            return []
        try:
            if update.callback_query is not None:
                actions = self._callback(update.callback_query)
            elif update.message is not None:
                actions = self._message(update.message, voice=voice, voice_error=voice_error)
            else:
                actions = []
            ProcessedTelegramUpdate.objects.filter(organization=self.organization, update_id=update.update_id).update(status="done")
            return actions
        except Exception:
            # Qayta yetkazilganda yana urinib ko'rish mumkin bo'lishi uchun belgini olib tashlaymiz;
            # xabarlar external_id bo'yicha baribir takrorlanmaydi.
            ProcessedTelegramUpdate.objects.filter(organization=self.organization, update_id=update.update_id).delete()
            raise
        finally:
            self._refresh_connections()

    # ------------------------------------------------------------------ handlers
    def _conversation(self, tg_message):
        user = tg_message.from_user
        return inbound.get_telegram_conversation(
            self.organization,
            chat_id=tg_message.chat.id,
            user_id=user.id,
            username=user.username or "",
            language=map_language(user.language_code),
        )

    def _replies_to_actions(self, conversation, replies: list[Message], keyboard: str | None = "main") -> list[OutgoingAction]:
        return [
            OutgoingAction(chat_id=int(conversation.external_chat_id), text=m.text, keyboard=keyboard, lang=conversation.language, message_id=m.id)
            for m in replies
            if m.text
        ]

    def _message(self, tg_message, *, voice=None, voice_error=None) -> list[OutgoingAction]:
        if tg_message.chat.type != "private" or tg_message.from_user is None or tg_message.from_user.is_bot:
            return []
        conversation = self._conversation(tg_message)
        chat_id = tg_message.chat.id
        text = (tg_message.text or "").strip()
        lang = conversation.language

        if text.startswith("/start"):
            greeting = inbound.greeting_message(conversation)
            return [
                OutgoingAction(chat_id=chat_id, text=t("choose_language", lang), keyboard="language", lang=lang),
                OutgoingAction(chat_id=chat_id, text=greeting.text, keyboard="main", lang=lang, message_id=greeting.id),
            ]
        if text in ("/lang", "/language") or text in LANGUAGE_BUTTON_TEXTS:
            return [OutgoingAction(chat_id=chat_id, text=t("choose_language", lang), keyboard="language", lang=lang)]
        if text == "/help":
            return [OutgoingAction(chat_id=chat_id, text=t("menu_hint", lang), keyboard="main", lang=lang)]

        external_id = f"tg:{tg_message.message_id}"
        if tg_message.voice is not None or tg_message.audio is not None:
            if voice_error:
                from apps.conversations import services as conv_services

                recorded = conv_services.record_customer_message(
                    conversation, text="[Ovozli xabar qabul qilinmadi]", kind=Message.Kind.VOICE, external_id=external_id
                )
                if recorded.duplicate:
                    return []
                Message.objects.filter(pk=recorded.message.pk).update(transcript_status=Message.TranscriptStatus.REJECTED)
                key = "voice_too_long" if voice_error in ("too_large", "too_long") else "voice_failed"
                reply = conv_services.add_outbound_message(conversation, sender=Message.Sender.AI, text=t(key, lang, seconds=settings.AUDIO_MAX_SECONDS))
                return self._replies_to_actions(conversation, [reply])
            if voice is None:
                return []
            result = inbound.process_voice(conversation, voice, external_id=external_id)
            return [] if result.duplicate else self._replies_to_actions(result.conversation, result.replies)

        if text:
            result = inbound.process_text(conversation, text, external_id=external_id)
            return [] if result.duplicate else self._replies_to_actions(result.conversation, result.replies)

        # Rasm, stiker va h.k. — faqat matn/ovoz qabul qilinadi
        return [OutgoingAction(chat_id=chat_id, text=t("menu_hint", lang), keyboard="main", lang=lang)]

    def _callback(self, callback) -> list[OutgoingAction]:
        data = callback.data or ""
        message = callback.message
        if not data.startswith("lang:") or message is None or callback.from_user is None:
            return [OutgoingAction(chat_id=0, callback_query_id=callback.id)]
        lang = data.split(":", 1)[1]
        conversation = inbound.get_telegram_conversation(
            self.organization,
            chat_id=message.chat.id,
            user_id=callback.from_user.id,
            username=callback.from_user.username or "",
            language=map_language(callback.from_user.language_code),
        )
        conversation = inbound.set_language(conversation, lang)
        return [
            OutgoingAction(chat_id=0, callback_query_id=callback.id),
            OutgoingAction(chat_id=message.chat.id, text=t("language_set", lang) + "\n\n" + t("menu_hint", lang), keyboard="main", lang=lang),
        ]
