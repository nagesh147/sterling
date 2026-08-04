"""Broker-side protective stop for auto-exec option longs (workstreams C / D).

The headline real-money bug was that a market BUY carries no stop — the trail
lived only in the UI. This places a *broker-side* GTT SELL at the trail price the
moment we enter, so the position is protected even if our server, the WS, or the
user's laptop dies. The tick monitor (monitor.py) complements it for intrabar
exits and trails the GTT up as the stop tightens.

GTT (Good-Till-Triggered) is the right primitive: it lives at Zerodha, survives
disconnects, and needs no resting margin. A stop alone is a single-leg GTT that
fires a market SELL of the full quantity when the premium falls to the trigger.

When the signal also carries a TARGET, both go into one **two-leg (OCO)** GTT
instead. That is the whole reason to use OCO here: the exchange cancels the
other leg when one fills, so "stop and target both fire and we sell twice" is
impossible by construction rather than by careful coding on our side. A target
enforced by our own tick monitor would be a second server-side sell path; this
is none.

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


def _oco_legs(trigger_premium: float, target_premium: float, direction: str) -> Optional[tuple]:
    """``(trigger_values, ordered_pair_is_stop_first)`` for a two-leg GTT, or None if
    the two levels cannot form a valid OCO.

    Kite requires the two trigger values in ASCENDING order, with each order leg in
    the matching position. For a long option the stop is below and the target above;
    for a short it is the other way round. If the "target" is not actually on the
    profitable side of the stop the pair is nonsense — return None and let the caller
    place a plain stop, rather than arming a target that would fire instantly.
    """
    stop, target = float(trigger_premium), float(target_premium)
    if stop <= 0 or target <= 0:
        return None
    if direction == "long" and target <= stop:
        return None
    if direction == "short" and target >= stop:
        return None
    lower, upper = (stop, target) if direction == "long" else (target, stop)
    return [lower, upper], direction == "long"


async def place_stop(client, *, tradingsymbol: str, exchange: str, qty: int,
                     trigger_premium: float, last_price: float,
                     direction: str = "long",
                     target_premium: float = 0.0) -> Optional[int]:
    """Place the broker-side exit for a position we just opened. Returns the
    trigger_id, or None on failure (caller falls back to the tick monitor).

    With ``target_premium`` set (and on the profitable side of the stop) this is a
    two-leg OCO carrying stop AND target; otherwise a single-leg stop.
    Direction-aware: long → SELL on downside, short → BUY on upside.
    """
    if qty <= 0 or trigger_premium <= 0:
        return None
    oco = _oco_legs(trigger_premium, target_premium, direction) if target_premium else None
    exit_leg = _exit_order(tradingsymbol, exchange, qty, direction)
    if oco:
        trigger_values, _stop_first = oco
        trigger_type = K.GTT_TYPE_OCO
        # Both legs exit the same position the same way; only the trigger differs, and
        # the exchange cancels whichever did not fire.
        orders = [dict(exit_leg), dict(exit_leg)]
    else:
        trigger_values = [float(trigger_premium)]
        trigger_type = K.GTT_TYPE_SINGLE
        orders = [exit_leg]
    try:
        res = await client.place_gtt(
            trigger_type=trigger_type,
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            last_price=float(last_price or trigger_premium),
            trigger_values=trigger_values,
            orders=orders,
        )
        tid = int((res or {}).get("trigger_id") or 0)
        return tid or None
    except Exception as exc:  # noqa: BLE001
        log.warning("kite protective GTT place failed for %s @ %.2f (target %.2f): %s",
                    tradingsymbol, trigger_premium, target_premium or 0.0, exc)
        return None


async def move_stop(client, *, trigger_id: int, tradingsymbol: str, exchange: str,
                    qty: int, trigger_premium: float, last_price: float,
                    direction: str = "long", target_premium: float = 0.0) -> bool:
    """Trail the GTT to a tighter ``trigger_premium``. Returns True on success.
    Direction-aware: uses the correct exit side for the GTT order leg.

    ``target_premium`` must be passed on every move for a position that HAS a target:
    a modify rewrites the whole trigger, so omitting it would silently downgrade an
    OCO to a bare stop and drop the target the first time the trail ratcheted.
    """
    if trigger_id <= 0 or trigger_premium <= 0:
        return False
    oco = _oco_legs(trigger_premium, target_premium, direction) if target_premium else None
    exit_leg = _exit_order(tradingsymbol, exchange, qty, direction)
    if oco:
        trigger_values, _stop_first = oco
        trigger_type, orders = K.GTT_TYPE_OCO, [dict(exit_leg), dict(exit_leg)]
    else:
        trigger_values, trigger_type, orders = [float(trigger_premium)], K.GTT_TYPE_SINGLE, [exit_leg]
    try:
        await client.modify_gtt(
            trigger_id,
            trigger_type=trigger_type,
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            last_price=float(last_price or trigger_premium),
            trigger_values=trigger_values,
            orders=orders,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("kite protective GTT modify failed for %s (#%s): %s",
                    tradingsymbol, trigger_id, exc)
        return False


#: What happened to a GTT we tried to cancel. The distinction is load-bearing:
#: "cancelled" means the broker stop is provably out of the way and it is safe to
#: place our own exit; anything else means a broker SELL may already be live for
#: this position, and placing a second one would sell twice and go net short.
CANCELLED = "cancelled"
GONE = "gone"        # already triggered, already deleted, or unknown to the broker
UNKNOWN = "unknown"  # the call failed and we cannot tell — treat as NOT cancelled

_GONE_MARKERS = ("not found", "does not exist", "no such", "already", "triggered",
                 "invalid trigger", "404")


async def cancel_stop_result(client, trigger_id: int) -> str:
    """Cancel a GTT and report which of the three outcomes above happened.

    The classification of a failure into GONE vs UNKNOWN is a heuristic over the
    broker's error text, because Kite's exact message for "this trigger already
    fired" is not something this repo can pin. That is fine as long as the caller
    treats BOTH as "not cancelled" — the distinction only changes the log line, never
    whether a second sell order goes out.
    """
    if trigger_id <= 0:
        return GONE  # nothing armed — nothing can double-fire
    try:
        await client.delete_gtt(trigger_id)
        return CANCELLED
    except Exception as exc:  # noqa: BLE001
        text = str(exc).lower()
        if any(marker in text for marker in _GONE_MARKERS):
            log.info("kite protective GTT #%s was already gone: %s", trigger_id, exc)
            return GONE
        log.warning("kite protective GTT cancel failed (#%s): %s", trigger_id, exc)
        return UNKNOWN


async def cancel_stop(client, trigger_id: int) -> bool:
    """True only when the GTT was provably cancelled by this call."""
    return (await cancel_stop_result(client, trigger_id)) == CANCELLED
