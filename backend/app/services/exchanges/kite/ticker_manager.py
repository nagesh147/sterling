"""
Per-user KiteTicker lifecycle + fan-out to the app WebSocket.

Each user gets at most one live :class:`KiteTicker` (built from their active,
connected Kite account). Decoded ticks are broadcast to the StreamManager channel
``kite_ticks:{user_id}`` so the frontend consumes them over the existing
``/api/v1/stream/ws`` socket — no second public socket to operate.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.core.logging import get_logger

from . import accounts as _accounts
from . import constants as K
from .ticker import KiteTicker

log = get_logger(__name__)

_tickers: Dict[str, KiteTicker] = {}


async def _warm_client(user_id: str):
    """Best-effort warm client for the user's active account (for monitor exits)."""
    try:
        acct = _accounts.get_active(user_id)
        if acct and acct.connected:
            return await _accounts.acquire_client(acct)
    except Exception as exc:  # noqa: BLE001
        log.debug("kite monitor client acquire failed for %s: %s", user_id, exc)
    return None


def _make_broadcaster(user_id: str):
    async def _broadcast(ticks: List[dict]) -> None:
        # Feed the tick-driven exit monitor FIRST (C/D) — a trail breach must
        # trigger a server-side exit regardless of whether any UI is listening.
        try:
            from app.services.kite_engine import monitor, positions
            if positions.open_positions(user_id):
                client = await _warm_client(user_id)
                if client is not None:
                    await monitor.on_ticks(user_id, ticks, client=client)
        except Exception as exc:  # never let the monitor kill the tick loop
            log.debug("kite monitor on_ticks failed for %s: %s", user_id, exc)
        # Then the ATM Premium Imbalance session, for the same reason: it enters
        # and exits on ticks, and must not depend on a UI being connected.
        try:
            from app.services import atm_premium_imbalance_runner as api_runner
            session = api_runner.active_session(user_id)
            if session is not None and not session.finished:
                client = await _warm_client(user_id)
                if client is not None:
                    await api_runner.on_ticks(
                        user_id, ticks, api_runner.KiteBrokerPort(client, session.pair)
                    )
        except Exception as exc:  # never let this kill the tick loop
            log.debug("ATM PI on_ticks failed for %s: %s", user_id, exc)
        try:
            from app.api.v1.endpoints.stream import stream_manager
            await stream_manager.broadcast_to_channel(
                f"kite_ticks:{user_id}",
                {"type": "kite_ticks", "ticks": ticks},
            )
        except Exception as exc:  # never let a broadcast error kill the tick loop
            log.debug("kite tick broadcast failed for %s: %s", user_id, exc)
    return _broadcast


def _make_order_broadcaster(user_id: str):
    async def _broadcast(order: dict) -> None:
        # Confirm fills / rejections against our position registry FIRST (E).
        # The client is passed because a REJECTED entry has to cancel the protective
        # GTT that was already armed for it — without a client the handler can only
        # log that an orphaned SELL is resting at Zerodha.
        try:
            from app.services.kite_engine import monitor
            await monitor.on_order_update(user_id, order, client=await _warm_client(user_id))
        except Exception as exc:  # never let the monitor kill the WS loop
            log.debug("kite monitor on_order_update failed for %s: %s", user_id, exc)
        try:
            from app.api.v1.endpoints.stream import stream_manager
            await stream_manager.broadcast_to_channel(
                f"kite_orders:{user_id}",
                {"type": "kite_order_update", "order": order},
            )
        except Exception as exc:  # never let a broadcast error kill the WS loop
            log.debug("kite order broadcast failed for %s: %s", user_id, exc)
    return _broadcast


async def broadcast_order_update(user_id: str, order: dict) -> None:
    """Push a single order update to the user's ``kite_orders`` channel.

    Used by both the live WS postback (text frames) and the HTTP postback webhook.
    """
    await _make_order_broadcaster(user_id)(order)


async def ensure(user_id: str) -> Optional[KiteTicker]:
    """Return a started ticker for the user's active connected account, or None."""
    existing = _tickers.get(user_id)
    if existing and existing.is_active:
        return existing
    acct = _accounts.get_active(user_id)
    if not acct or not acct.connected or acct.is_paper:
        return None
    ticker = KiteTicker(
        api_key=acct.api_key, access_token=acct.access_token,
        on_ticks=_make_broadcaster(user_id),
        on_order_update=_make_order_broadcaster(user_id),
    )
    _tickers[user_id] = ticker
    await ticker.start()
    return ticker


async def subscribe(user_id: str, tokens: List[int], mode: str = K.MODE_QUOTE) -> dict:
    ticker = await ensure(user_id)
    if not ticker:
        return {"ok": False, "message": "No connected (live) Kite account — log in first."}
    await ticker.subscribe(tokens, mode)
    return {"ok": True, **ticker.status()}


async def unsubscribe(user_id: str, tokens: List[int]) -> dict:
    ticker = _tickers.get(user_id)
    if not ticker:
        return {"ok": True, "message": "No active ticker"}
    await ticker.unsubscribe(tokens)
    return {"ok": True, **ticker.status()}


async def stop(user_id: str) -> dict:
    ticker = _tickers.pop(user_id, None)
    if ticker:
        await ticker.stop()
    return {"ok": True}


def status(user_id: str) -> dict:
    ticker = _tickers.get(user_id)
    if not ticker:
        return {"active": False, "connected": False, "subscribed": [], "tick_count": 0}
    return ticker.status()


async def stop_all() -> None:
    for uid in list(_tickers.keys()):
        await stop(uid)


def clear() -> None:
    """Test hook — drop references without awaiting (no live sockets in tests)."""
    _tickers.clear()
