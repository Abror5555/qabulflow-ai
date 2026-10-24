"""aiogram 3 adapteri: klaviaturalar, polling dispatcher, webhook va xabar yuborish."""

from __future__ import annotations

import asyncio
import io
import logging

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

from apps.ai_agent.stt import AudioInput
from apps.ai_agent.texts import t
from apps.integrations.telegram.processor import OutgoingAction, TelegramProcessor

logger = logging.getLogger(__name__)


def main_keyboard(lang: str):
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    rows = [
        [t("btn_trial", lang)],
        [t("btn_courses", lang), t("btn_prices", lang)],
        [t("btn_branches", lang), t("btn_schedule", lang)],
        [t("btn_my_bookings", lang), t("btn_admin", lang)],
        [t("btn_language", lang)],
    ]
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in row] for row in rows], resize_keyboard=True)


def language_keyboard():
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
            ]
        ]
    )


def _keyboard(action: OutgoingAction):
    if action.keyboard == "main":
        return main_keyboard(action.lang)
    if action.keyboard == "language":
        return language_keyboard()
    return None


@sync_to_async
def _mark_delivery(message_id: int, ok: bool, external_id: str = "") -> None:
    from apps.conversations.models import Message
    from apps.notifications.models import OutboxMessage

    msg = Message.objects.filter(pk=message_id).select_related("conversation").first()
    if msg is None:
        return
    Message.objects.filter(pk=message_id).update(delivery_status="sent" if ok else "failed")
    OutboxMessage.objects.get_or_create(
        dedup_key=f"msg:{message_id}",
        defaults={
            "organization_id": msg.organization_id,
            "channel": "telegram",
            "recipient": msg.conversation.external_chat_id,
            "text": msg.text,
            "message": msg,
            "status": "sent" if ok else "failed",
            "attempts": 1,
            "external_message_id": external_id,
            "sent_at": timezone.now() if ok else None,
        },
    )


async def send_actions(bot, actions: list[OutgoingAction]) -> None:
    for action in actions:
        if action.callback_query_id:
            try:
                await bot.answer_callback_query(action.callback_query_id)
            except Exception:  # noqa: BLE001
                logger.warning("callback javobi yuborilmadi")
        if not action.text or not action.chat_id:
            continue
        try:
            sent = await bot.send_message(action.chat_id, action.text, reply_markup=_keyboard(action))
            if action.message_id:
                await _mark_delivery(action.message_id, True, str(sent.message_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram xabari yuborilmadi: %s", exc.__class__.__name__)
            if action.message_id:
                await _mark_delivery(action.message_id, False)


async def download_voice(bot, tg_message) -> tuple[AudioInput | None, str | None]:
    media = tg_message.voice or tg_message.audio
    if media is None:
        return None, None
    if (media.file_size or 0) > settings.AUDIO_MAX_BYTES:
        return None, "too_large"
    if (media.duration or 0) > settings.AUDIO_MAX_SECONDS:
        return None, "too_long"
    buffer = io.BytesIO()
    try:
        await bot.download(media, destination=buffer)
    except Exception:  # noqa: BLE001
        logger.warning("Ovozli fayl yuklab olinmadi")
        return None, "download_failed"
    return AudioInput(data=buffer.getvalue(), content_type=media.mime_type or "audio/ogg", duration_seconds=float(media.duration or 0) or None), None


async def handle_update(bot, update, processor: TelegramProcessor | None = None) -> None:
    processor = processor or await sync_to_async(TelegramProcessor)()
    voice, voice_error = (None, None)
    if update.message is not None and (update.message.voice or update.message.audio):
        voice, voice_error = await download_voice(bot, update.message)
    actions = await sync_to_async(processor.process)(update, voice=voice, voice_error=voice_error)
    await send_actions(bot, actions)


def build_dispatcher():
    from aiogram import Dispatcher, Router
    from aiogram.types import Update

    router = Router(name="qabulflow")
    dp = Dispatcher()

    @dp.update.outer_middleware()
    async def _route_all(handler, event: Update, data):  # noqa: ANN001
        bot = data["bot"]
        try:
            await handle_update(bot, event)
        except Exception:  # noqa: BLE001
            logger.exception("Telegram update ishlovida xato")
        return None

    dp.include_router(router)
    return dp


async def run_polling() -> None:
    from aiogram import Bot

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=False)
    me = await bot.get_me()
    logger.info("Telegram bot @%s long polling rejimida ishga tushdi", me.username)
    await build_dispatcher().start_polling(bot, allowed_updates=["message", "callback_query"])


def process_webhook_payload(payload: dict) -> int:
    """Webhook view'idan chaqiriladi (sinxron kontekst)."""

    from aiogram import Bot
    from aiogram.types import Update

    async def _run():
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        try:
            update = Update.model_validate(payload, context={"bot": bot})
            await handle_update(bot, update)
        finally:
            await bot.session.close()
        return update.update_id

    return asyncio.run(_run())
