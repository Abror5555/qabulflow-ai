"""Outbox (Celery) uchun sinxron Telegram yuboruvchi. Faqat token bor va DEMO_MODE o'chiq bo'lsa chaqiriladi."""

from __future__ import annotations

import asyncio

from django.conf import settings


def send_telegram_text(chat_id: str, text: str) -> str:
    if not settings.TELEGRAM_BOT_TOKEN or settings.DEMO_MODE:
        raise RuntimeError("Telegram yuborish o'chirilgan (token yo'q yoki DEMO_MODE)")
    from aiogram import Bot

    async def _send():
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        try:
            msg = await bot.send_message(int(chat_id), text)
            return str(msg.message_id)
        finally:
            await bot.session.close()

    return asyncio.run(_send())


def get_bot_info() -> dict:
    from aiogram import Bot

    async def _me():
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        try:
            me = await bot.get_me()
            info = await bot.get_webhook_info()
            return {"username": me.username, "id": me.id, "webhook_url_set": bool(info.url)}
        finally:
            await bot.session.close()

    return asyncio.run(_me())
