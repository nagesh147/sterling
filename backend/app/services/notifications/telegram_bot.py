"""Telegram transport and command dispatcher for the Zerodha/Kite desk."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from app.services.notifications import telegram as _tg

log = logging.getLogger(__name__)
_API = "https://api.telegram.org"


async def _api(method: str, payload: dict, timeout: float = 35.0) -> dict:
    if not _tg.TELEGRAM_TOKEN:
        return {}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_API}/bot{_tg.TELEGRAM_TOKEN}/{method}",
                json=payload,
                timeout=timeout,
            )
        return response.json() if response.status_code == 200 else {}
    except Exception as exc:
        log.debug("telegram API %s error: %s", method, exc)
        return {}


async def _send(text: str, chat_id: str, reply_markup: Optional[dict] = None) -> dict:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _api("sendMessage", payload)


async def _edit(
    chat_id: str,
    message_id: int,
    text: str,
    reply_markup: Optional[dict] = None,
) -> dict:
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _api("editMessageText", payload)


async def _answer_cb(callback_id: str, text: str = "") -> None:
    await _api("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
    })


def _btn(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data}


async def _handle_update(update: dict) -> None:
    configured_chat = str(_tg.TELEGRAM_CHAT_ID or "")
    if "message" in update:
        message = update["message"]
        chat_id = str(message.get("chat", {}).get("id", ""))
        if configured_chat and chat_id != configured_chat:
            return
        from app.services.notifications import telegram_kite
        await telegram_kite.handle_kite_command(chat_id)
        return

    if "callback_query" in update:
        callback = update["callback_query"]
        chat_id = str(callback.get("message", {}).get("chat", {}).get("id", ""))
        callback_id = callback.get("id", "")
        if configured_chat and chat_id != configured_chat:
            await _answer_cb(callback_id)
            return
        from app.services.notifications import telegram_kite
        await telegram_kite.handle_kite_callback(
            chat_id,
            callback["message"]["message_id"],
            callback_id,
            callback.get("data", ""),
        )


async def poll_loop() -> None:
    """Long-poll Telegram and dispatch every authorized update to the Kite desk."""
    offset = 0
    log.info("Kite Telegram poll loop started")
    while True:
        if not _tg.TELEGRAM_TOKEN:
            await asyncio.sleep(15)
            continue
        try:
            response = await _api(
                "getUpdates",
                {"offset": offset, "timeout": 30},
                timeout=40,
            )
            for update in response.get("result", []):
                offset = max(offset, update.get("update_id", 0) + 1)
                try:
                    await _handle_update(update)
                except Exception as exc:
                    log.warning("Telegram update handler error: %s", exc)
        except Exception as exc:
            log.debug("Telegram getUpdates error: %s", exc)
            await asyncio.sleep(5)

