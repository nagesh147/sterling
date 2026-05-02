import httpx
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


async def send(text: str, parse_mode: str = "HTML",
               reply_markup: dict | None = None) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": parse_mode,
                    "reply_markup": reply_markup,
                },
                timeout=5,
            )
        return r.status_code == 200
    except Exception:
        return False
