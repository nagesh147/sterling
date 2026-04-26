"""
In-memory webhook store + async delivery + SQLite persistence.
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
_loaded = False


def _new_id() -> str:
    return uuid.uuid4().hex[:8].upper()


# ─── SQLite persistence ───────────────────────────────────────────────────────

def _persist(wh: WebhookConfig) -> None:
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("""
                INSERT OR REPLACE INTO webhooks
                    (id, name, webhook_type, url, extra, active,
                     created_at_ms, last_triggered_ms, trigger_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                wh.id, wh.name, wh.webhook_type.value, wh.url,
                json.dumps(wh.extra), int(wh.active),
                wh.created_at_ms, wh.last_triggered_ms, wh.trigger_count,
            ))
    except Exception as exc:
        log.warning("webhook persist failed: %s", exc)


def _delete_db(wh_id: str) -> None:
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("DELETE FROM webhooks WHERE id = ?", (wh_id,))
    except Exception as exc:
        log.warning("webhook delete failed: %s", exc)


def _load_from_db() -> List[WebhookConfig]:
    from app.services import db
    if not db._available:
        return []
    try:
        with db._conn() as c:
            rows = c.execute("SELECT * FROM webhooks").fetchall()
        result = []
        for r in rows:
            try:
                result.append(WebhookConfig(
                    id=r["id"], name=r["name"],
                    webhook_type=WebhookType(r["webhook_type"]),
                    url=r["url"],
                    extra=json.loads(r["extra"] or "{}"),
                    active=bool(r["active"]),
                    created_at_ms=r["created_at_ms"],
                    last_triggered_ms=r["last_triggered_ms"],
                    trigger_count=r["trigger_count"] or 0,
                ))
            except Exception:
                continue
        return result
    except Exception as exc:
        log.warning("webhook load failed: %s", exc)
        return []


def bootstrap() -> None:
    """Load persisted webhooks from DB at startup."""
    global _loaded
    if _loaded:
        return
    for wh in _load_from_db():
        _webhooks[wh.id] = wh
    if _webhooks:
        log.info("Loaded %d webhooks from DB", len(_webhooks))
    _loaded = True


# ─── CRUD ─────────────────────────────────────────────────────────────────────

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
    _persist(wh)
    return wh


def get_webhook(wh_id: str) -> Optional[WebhookConfig]:
    return _webhooks.get(wh_id)


def list_webhooks() -> List[WebhookConfig]:
    return list(_webhooks.values())


def delete_webhook(wh_id: str) -> bool:
    if wh_id not in _webhooks:
        return False
    del _webhooks[wh_id]
    _delete_db(wh_id)
    return True


def update_webhook(wh_id: str, **kwargs) -> Optional[WebhookConfig]:
    wh = _webhooks.get(wh_id)
    if not wh:
        return None
    updated = wh.model_copy(update=kwargs)
    _webhooks[wh_id] = updated
    _persist(updated)
    return updated


def clear() -> None:
    _webhooks.clear()


# ─── Delivery ─────────────────────────────────────────────────────────────────

async def deliver(wh_id: str, subject: str, message: str, data: dict = None) -> bool:
    wh = _webhooks.get(wh_id)
    if not wh or not wh.active:
        return False
    try:
        ok = await _send(wh, subject, message, data or {})
        now_ms = int(time.time() * 1000)
        updated = wh.model_copy(update={
            "last_triggered_ms": now_ms,
            "trigger_count": wh.trigger_count + 1,
        })
        _webhooks[wh_id] = updated
        _persist(updated)
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
