import httpx
import os
import logging

log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


async def send(text: str, parse_mode: str = "HTML",
               reply_markup: dict | None = None) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    payload: dict = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }
    # Telegram returns 400 "object expected as reply markup" if the field is null
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json=payload,
                timeout=8,
            )
        if r.status_code != 200:
            log.warning("Telegram sendMessage failed %s: %s", r.status_code, r.text[:200])
        return r.status_code == 200
    except Exception as exc:
        log.warning("Telegram send error: %s", exc)
        return False
