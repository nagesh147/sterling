"""
Per-user Kite-specific Telegram alert targets — store + transport.

Kite gets its OWN Telegram (separate bot(s)/chat from the crypto global one). A
user can register multiple alert *targets*, each a ``{bot_token, chat_id}`` pair.

Persistence is JSON in the app DB config store (``db.set_config``/``get_config``)
under a per-user key (``kite_tg_targets:{user_id}``). Bot tokens are encrypted at
rest with the SAME util the Kite account credentials use
(:mod:`app.core.security`) — never invent new crypto, never store a raw token.

Responses expose only ``bot_token_hint`` (last 6 chars) + ``bot_token_set`` — the
raw token never leaves this layer except to :func:`send_via`.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import List, Optional

import httpx

from app.core.logging import get_logger
from app.core.security import decrypt, encrypt
from app.services import db

log = get_logger(__name__)

_KEY_PREFIX = "kite_tg_targets:"
_TG_API = "https://api.telegram.org/bot{token}/sendMessage"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _key(user_id: str) -> str:
    return f"{_KEY_PREFIX}{user_id}"


@dataclass
class Target:
    """One Kite alert destination. ``bot_token_enc`` is encrypted at rest."""
    id: str
    label: str = ""
    chat_id: str = ""
    bot_token_enc: str = ""
    enabled: bool = True
    reachable: bool = False
    created_at_ms: int = field(default_factory=_now_ms)
    updated_at_ms: int = field(default_factory=_now_ms)

    # ── derived ──
    @property
    def bot_token(self) -> str:
        return decrypt(self.bot_token_enc)

    @property
    def bot_token_set(self) -> bool:
        return bool(self.bot_token_enc)

    def token_hint(self) -> str:
        tok = self.bot_token
        if not tok:
            return ""
        return tok[-6:]


# ─── persistence (JSON in system_config) ──────────────────────────────────────
def _load_raw(user_id: str) -> List[Target]:
    raw = db.get_config(_key(user_id), "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        log.warning("kite_tg_targets corrupt JSON for user %s — resetting", user_id)
        return []
    out: List[Target] = []
    for d in data if isinstance(data, list) else []:
        if not isinstance(d, dict) or not d.get("id"):
            continue
        out.append(Target(
            id=str(d.get("id")),
            label=str(d.get("label", "")),
            chat_id=str(d.get("chat_id", "")),
            bot_token_enc=str(d.get("bot_token_enc", "")),
            enabled=bool(d.get("enabled", True)),
            reachable=bool(d.get("reachable", False)),
            created_at_ms=int(d.get("created_at_ms") or _now_ms()),
            updated_at_ms=int(d.get("updated_at_ms") or _now_ms()),
        ))
    return out


def _save_raw(user_id: str, targets: List[Target]) -> None:
    db.set_config(_key(user_id), json.dumps([asdict(t) for t in targets]))


# ─── CRUD (user-scoped) ───────────────────────────────────────────────────────
def list_targets(user_id: str) -> List[Target]:
    return _load_raw(user_id)


def get(user_id: str, target_id: str) -> Optional[Target]:
    return next((t for t in _load_raw(user_id) if t.id == target_id), None)


def enabled_targets(user_id: str) -> List[Target]:
    return [t for t in _load_raw(user_id) if t.enabled and t.bot_token_enc and t.chat_id]


def add(user_id: str, *, label: str, bot_token: str, chat_id: str, enabled: bool = True) -> Target:
    targets = _load_raw(user_id)
    t = Target(
        id=uuid.uuid4().hex,
        label=label or "",
        chat_id=chat_id or "",
        bot_token_enc=encrypt(bot_token) if bot_token else "",
        enabled=enabled,
    )
    targets.append(t)
    _save_raw(user_id, targets)
    return t


def update(user_id: str, target_id: str, *, label: Optional[str] = None,
           bot_token: Optional[str] = None, chat_id: Optional[str] = None,
           enabled: Optional[bool] = None) -> Optional[Target]:
    targets = _load_raw(user_id)
    t = next((x for x in targets if x.id == target_id), None)
    if t is None:
        return None
    if label is not None:
        t.label = label
    if chat_id is not None:
        t.chat_id = chat_id
    # Omitted OR empty bot_token keeps the existing stored token (don't wipe it).
    if bot_token:
        t.bot_token_enc = encrypt(bot_token)
    if enabled is not None:
        t.enabled = enabled
    t.updated_at_ms = _now_ms()
    _save_raw(user_id, targets)
    return t


def set_reachable(user_id: str, target_id: str, reachable: bool) -> Optional[Target]:
    targets = _load_raw(user_id)
    t = next((x for x in targets if x.id == target_id), None)
    if t is None:
        return None
    t.reachable = reachable
    t.updated_at_ms = _now_ms()
    _save_raw(user_id, targets)
    return t


def delete(user_id: str, target_id: str) -> bool:
    targets = _load_raw(user_id)
    kept = [t for t in targets if t.id != target_id]
    if len(kept) == len(targets):
        return False
    _save_raw(user_id, kept)
    return True


# ─── transport ────────────────────────────────────────────────────────────────
async def send_via(token: str, chat_id: str, html: str) -> bool:
    """POST a HTML message to a specific bot token + chat. Returns success bool;
    swallows/logs errors so a dead target never breaks the alert loop."""
    if not (token and chat_id):
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _TG_API.format(token=token),
                json={"chat_id": chat_id, "text": html, "parse_mode": "HTML"},
            )
        if resp.status_code == 200 and resp.json().get("ok"):
            return True
        log.warning("kite telegram send_via failed (%s): %s", resp.status_code, resp.text[:200])
        return False
    except Exception as exc:  # noqa: BLE001
        log.warning("kite telegram send_via error: %s", exc)
        return False
