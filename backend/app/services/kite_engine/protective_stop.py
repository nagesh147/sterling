"""Broker-side protective stop for auto-exec option longs (workstreams C / D).

The headline real-money bug was that a market BUY carries no stop — the trail
lived only in the UI. This places a *broker-side* GTT SELL at the trail price the
moment we enter, so the position is protected even if our server, the WS, or the
user's laptop dies. The tick monitor (monitor.py) complements it for intrabar
exits and trails the GTT up as the stop tightens.

GTT (Good-Till-Triggered) is the right primitive: it lives at Zerodha, survives
disconnects, and needs no resting margin. We use a single-leg GTT that fires a
market SELL of the full quantity when the premium falls to the trigger.

Thin I/O wrappers around the KiteClient GTT surface; all calls are defensive
(never raise into the caller — a failed stop is logged, not fatal, and the tick
monitor remains as the backstop).
"""
from __future__ import annotations

from typing import Optional

from app.core.logging import get_logger
from app.services.exchanges.kite import constants as K

log = get_logger(__name__)


def _exit_order(tradingsymbol: str, exchange: str, qty: int, direction: str = "long") -> dict:
    """One GTT order leg: market exit of the full quantity.
    Long position → SELL to exit. Short position → BUY to cover."""
    txn = K.TXN_SELL if direction == "long" else K.TXN_BUY
    return {
        "exchange": exchange,
        "tradingsymbol": tradingsymbol,
        "transaction_type": txn,
        "quantity": int(qty),
        "order_type": K.ORDER_TYPE_MARKET,
        "product": K.PRODUCT_NRML,
    }


async def place_stop(client, *, tradingsymbol: str, exchange: str, qty: int,
                     trigger_premium: float, last_price: float,
                     direction: str = "long") -> Optional[int]:
    """Place a single-leg GTT stop at ``trigger_premium``. Returns the
    trigger_id, or None on failure (caller falls back to the tick monitor).
    Direction-aware: long → SELL on downside, short → BUY on upside."""
    if qty <= 0 or trigger_premium <= 0:
        return None
    try:
        res = await client.place_gtt(
            trigger_type=K.GTT_TYPE_SINGLE,
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            last_price=float(last_price or trigger_premium),
            trigger_values=[float(trigger_premium)],
            orders=[_exit_order(tradingsymbol, exchange, qty, direction)],
        )
        tid = int((res or {}).get("trigger_id") or 0)
        return tid or None
    except Exception as exc:  # noqa: BLE001
        log.warning("kite protective GTT place failed for %s @ %.2f: %s",
                    tradingsymbol, trigger_premium, exc)
        return None


async def move_stop(client, *, trigger_id: int, tradingsymbol: str, exchange: str,
                    qty: int, trigger_premium: float, last_price: float,
                    direction: str = "long") -> bool:
    """Trail the GTT to a tighter ``trigger_premium``. Returns True on success.
    Direction-aware: uses the correct exit side for the GTT order leg."""
    if trigger_id <= 0 or trigger_premium <= 0:
        return False
    try:
        await client.modify_gtt(
            trigger_id,
            trigger_type=K.GTT_TYPE_SINGLE,
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            last_price=float(last_price or trigger_premium),
            trigger_values=[float(trigger_premium)],
            orders=[_exit_order(tradingsymbol, exchange, qty, direction)],
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("kite protective GTT modify failed for %s (#%s): %s",
                    tradingsymbol, trigger_id, exc)
        return False


async def cancel_stop(client, trigger_id: int) -> bool:
    """Cancel a GTT (after a monitor-driven exit, so it can't double-fire)."""
    if trigger_id <= 0:
        return False
    try:
        await client.delete_gtt(trigger_id)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("kite protective GTT cancel failed (#%s): %s", trigger_id, exc)
        return False
