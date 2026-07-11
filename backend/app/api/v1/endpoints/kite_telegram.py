"""
Kite-specific Telegram alert targets — per-user CRUD + test.

Kite gets its OWN Telegram (separate bot(s)/chat from the crypto global one). Each
user can register multiple alert *targets* (``{bot_token, chat_id}``); enabled
targets receive the Kite engine's outbound signal alerts (see
``services/notifications/telegram_kite.py::push_kite_alerts``).

Every route is scoped to the calling user (``get_current_user``), mirroring
``kite.py``. Bot tokens are encrypted at rest (reusing the Kite-account credential
encryption) and NEVER returned raw — responses expose only a 6-char hint.

This part is OUTBOUND alerts + test + management only; the interactive ``/kite``
control bot stays on the shared crypto bot.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import UserContext, get_current_user
from app.core.logging import get_logger
from app.services.notifications import kite_telegram_store as store

log = get_logger(__name__)
router = APIRouter(prefix="/kite/telegram", tags=["kite"])


# ─── Schemas ──────────────────────────────────────────────────────────────────
class TargetIn(BaseModel):
    label: str
    bot_token: str
    chat_id: str
    enabled: bool = True


class TargetPatch(BaseModel):
    label: Optional[str] = None
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    enabled: Optional[bool] = None


class TargetOut(BaseModel):
    id: str
    label: str
    chat_id: str
    bot_token_hint: str
    bot_token_set: bool
    enabled: bool
    reachable: bool


class TargetListResponse(BaseModel):
    targets: List[TargetOut]


class OkResponse(BaseModel):
    ok: bool = True


def _to_out(t: "store.Target") -> TargetOut:
    return TargetOut(
        id=t.id,
        label=t.label,
        chat_id=t.chat_id,
        bot_token_hint=t.token_hint(),
        bot_token_set=t.bot_token_set,
        enabled=t.enabled,
        reachable=t.reachable,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────
@router.get("")
async def list_targets(user: UserContext = Depends(get_current_user)) -> TargetListResponse:
    return TargetListResponse(targets=[_to_out(t) for t in store.list_targets(user.user_id)])


@router.post("")
async def create_target(body: TargetIn, user: UserContext = Depends(get_current_user)) -> TargetOut:
    t = store.add(
        user.user_id,
        label=body.label,
        bot_token=body.bot_token,
        chat_id=body.chat_id,
        enabled=body.enabled,
    )
    return _to_out(t)


@router.put("/{target_id}")
async def update_target(target_id: str, body: TargetPatch,
                        user: UserContext = Depends(get_current_user)) -> TargetOut:
    t = store.update(
        user.user_id, target_id,
        label=body.label, bot_token=body.bot_token,
        chat_id=body.chat_id, enabled=body.enabled,
    )
    if t is None:
        raise HTTPException(404, "Kite telegram target not found")
    return _to_out(t)


@router.delete("/{target_id}")
async def delete_target(target_id: str, user: UserContext = Depends(get_current_user)) -> OkResponse:
    if not store.delete(user.user_id, target_id):
        raise HTTPException(404, "Kite telegram target not found")
    return OkResponse(ok=True)


@router.post("/{target_id}/test")
async def test_target(target_id: str, user: UserContext = Depends(get_current_user)) -> TargetOut:
    t = store.get(user.user_id, target_id)
    if t is None:
        raise HTTPException(404, "Kite telegram target not found")
    if not (t.bot_token_set and t.chat_id):
        raise HTTPException(400, "Target is missing a bot token or chat id.")
    label = t.label or "Kite alerts"
    ok = await store.send_via(
        t.bot_token, t.chat_id,
        f"✅ Kite alerts connected — <b>{label}</b>",
    )
    updated = store.set_reachable(user.user_id, target_id, ok) or t
    return _to_out(updated)
