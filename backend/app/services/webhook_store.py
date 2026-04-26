"""
In-memory webhook store + async delivery.
Supports: Discord, Telegram, generic HTTP POST.
"""
import json
import time
import uuid
from typing import Dict, List, Optional

import httpx

from app.schemas.webhooks import WebhookConfig, WebhookCreate, WebhookType
from app.core.logging import get_logger

log = get_logger(__name__)

_webhooks: Dict[str, WebhookConfig] = {}


def _new_id() -> str:
    return uuid.uuid4().hex[:8].upper()


def add_webhook(data: WebhookCreate) -> WebhookConfig:
    wh = WebhookConfig(
        id=_new_id(),
        name=data.name,
        webhook_type=data.webhook_type,
        url=data.url,
        extra=data.extra,
        active=data.active,
        created_at_ms=int(time.time() * 1000),
    )
    _webhooks[wh.id] = wh
    return wh


def get_webhook(wh_id: str) -> Optional[WebhookConfig]:
    return _webhooks.get(wh_id)


def list_webhooks() -> List[WebhookConfig]:
    return list(_webhooks.values())


def delete_webhook(wh_id: str) -> bool:
    if wh_id not in _webhooks:
        return False
    del _webhooks[wh_id]
    return True


def update_webhook(wh_id: str, **kwargs) -> Optional[WebhookConfig]:
    wh = _webhooks.get(wh_id)
    if not wh:
        return None
    updated = wh.model_copy(update=kwargs)
    _webhooks[wh_id] = updated
    return updated


def clear() -> None:
    _webhooks.clear()


async def deliver(wh_id: str, subject: str, message: str, data: dict = None) -> bool:
    wh = _webhooks.get(wh_id)
    if not wh or not wh.active:
        return False
    try:
        ok = await _send(wh, subject, message, data or {})
        now_ms = int(time.time() * 1000)
        _webhooks[wh_id] = wh.model_copy(update={
            "last_triggered_ms": now_ms,
            "trigger_count": wh.trigger_count + 1,
        })
        return ok
    except Exception as exc:
        log.warning("Webhook delivery failed %s: %s", wh_id, exc)
        return False


async def deliver_all(subject: str, message: str, data: dict = None) -> int:
    """Send to all active webhooks. Returns count delivered."""
    count = 0
    for wh_id in list(_webhooks.keys()):
        if await deliver(wh_id, subject, message, data):
            count += 1
    return count


async def _send(wh: WebhookConfig, subject: str, message: str, data: dict) -> bool:
    if wh.webhook_type == WebhookType.DISCORD:
        payload = {
            "content": None,
            "embeds": [{
                "title": f"🔔 Sterling — {subject}",
                "description": message,
                "color": 0x44cc88 if "ARROW" in subject.upper() or "TRIGGERED" in subject.upper() else 0x88aaff,
                "footer": {"text": f"Sterling Paper Trading | {data.get('underlying', '')}"},
            }]
        }
    elif wh.webhook_type == WebhookType.TELEGRAM:
        chat_id = wh.extra.get("chat_id", "")
        payload = {"chat_id": chat_id, "text": f"🔔 *Sterling — {subject}*\n{message}", "parse_mode": "Markdown"}
    else:
        payload = {"subject": subject, "message": message, "data": data}

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.post(wh.url, json=payload)
        resp.raise_for_status()
    return True
