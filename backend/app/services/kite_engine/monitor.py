"""Tick-driven exit + fill tracking for auto-exec option positions (C / D / E).

Two event handlers, both fed by the existing per-user KiteTicker WS — no polling:

  * ``on_tick`` (C/D): for every price tick on a held contract, exit at market the
    moment the premium breaches the trail. This is intrabar and independent of the
    5-minute scan, so a fast collapse no longer rides unprotected between scans.
    When a broker GTT also guards the position, the monitor cancels it after its
    own exit so the stop can't double-fire.

  * ``on_order_update`` (E): consume Kite order postbacks to confirm fills (stamp
    the real average fill price), and to mark COMPLETE/REJECTED instead of assuming
    the entry succeeded.

The monitor holds no scheduling of its own; it reacts to WS callbacks. The order
exit itself is a market SELL of the held quantity via the warm client.
"""
from __future__ import annotations

from typing import Optional

from app.core.logging import get_logger
from app.engines.common.exit_counter import get_exit_threshold
from app.services.kite_engine import positions as pos
from app.services.kite_engine import protective_stop as pstop
from app.services.kite_engine import state

log = get_logger(__name__)


# Kite order "status" values that mean the entry will never fill.
_DEAD_STATUSES = {"REJECTED", "CANCELLED"}
_FILLED_STATUS = "COMPLETE"


async def on_order_update(uid: str, order: dict, *, client=None) -> None:
    """Handle one Kite order postback for ``uid`` (workstream E).

    Matches the postback to a registered position by tradingsymbol and updates its
    fill price / status. Unknown orders (manual trades, other strategies) are
    ignored. Never raises — a bad postback must not kill the WS loop.
    """
    try:
        symbol = str(order.get("tradingsymbol", "")).strip()
        if not symbol:
            return
        p = pos.get(uid, symbol)
        if p is None:
            return  # not one of ours
        status = str(order.get("status", "")).upper()
        if status == _FILLED_STATUS:
            avg = float(order.get("average_price") or 0.0)
            pos.mark_filled(uid, symbol, avg)
            state.log(uid, "info",
                      f"Fill confirmed: {symbol} @ ₹{avg:.2f} (#{order.get('order_id', '')})")
        elif status in _DEAD_STATUSES:
            pos.mark_rejected(uid, symbol, reason=str(order.get("status_message") or status))
            # Entry never filled → release the auto-open guard so the slot can re-enter.
            if p.guard_key:
                state.clear_auto_open(uid, p.guard_key)
            state.log(uid, "order_failed", f"{symbol} {status.lower()} — guard released")
    except Exception as exc:  # noqa: BLE001
        log.debug("kite monitor on_order_update error for %s: %s", uid, exc)


async def _exit_position(client, uid: str, p: pos.OpenPosition, ltp: float, reason: Optional[str] = None) -> None:
    """Market-exit the full quantity and cancel any broker GTT (trail breach or red count).
    For options: always SELL. For futures: exit = opposite side (SELL if long, BUY if short)."""
    is_futures = p.vehicle == "futures"
    exit_side = "sell" if p.direction == "long" else "buy"
    try:
        if is_futures:
            await client.place_order_future(
                p.symbol, exit_side, p.qty, exchange=p.exchange,
                tag=f"trailexit:{p.symbol}")
        else:
            await client.place_order_option(
                p.symbol, "sell", p.qty, exchange=p.exchange,
                tag=f"trailexit:{p.symbol}")
    except Exception as exc:  # noqa: BLE001
        state.log(uid, "order_failed", f"Trail exit {exit_side.upper()} {p.symbol} failed: {exc}")
        return
    if p.gtt_id:
        await pstop.cancel_stop(client, p.gtt_id)
    breach_dir = "≥" if p.direction == "short" else "≤"
    close_reason = reason or f"trail breach @ ₹{ltp:.2f} {breach_dir} ₹{p.stop_premium:.2f}"
    pos.close(uid, p.symbol, reason=close_reason)
    if p.guard_key:
        state.clear_auto_open(uid, p.guard_key)
    state.log(uid, "order_placed",
              f"{exit_side.upper()} {p.qty} {p.symbol} @ market — {close_reason}")
    # Unsubscribe the token now that we no longer hold this position.
    if p.token:
        try:
            from app.services.exchanges.kite import ticker_manager
            await ticker_manager.unsubscribe(uid, [p.token])
        except Exception:  # noqa: BLE001
            pass


async def on_tick(uid: str, token: int, ltp: float, *, client) -> Optional[str]:
    """Handle one price tick (workstream C/D). Returns the symbol exited, or None.

    Finds the held position for ``token`` and exits at market if the premium has
    breached its trail. A position still pending its fill is not exited (we don't
    yet hold it).
    """
    try:
        for p in pos.open_positions(uid):
            if p.token != token:
                continue
            if p.status != pos.OPEN:
                return None  # not filled yet — nothing to protect
            # Price trail breach (original)
            price_exit = pos.should_exit(p.stop_premium, ltp, p.direction)
            # Red-count awareness (shared logic): if last scan reported enough reds for this position's entry-time exit_mode, exit.
            # This makes the 1/2/3-red (or +signal) counter drive auto-exits dynamically on live positions.
            reds = getattr(p, 'current_red_count', 0)
            mode = getattr(p, 'exit_mode', 'one_red')
            thresh = get_exit_threshold(mode)
            red_exit = reds >= thresh
            if price_exit or red_exit:
                close_reason = f"trail breach @ ₹{ltp:.2f} { '≤' if p.direction == 'long' else '≥' } ₹{p.stop_premium:.2f}" if price_exit else f"red count exit {reds}/{thresh} ({mode})"
                await _exit_position(client, uid, p, ltp, reason=close_reason)
                return p.symbol
            return None
    except Exception as exc:  # noqa: BLE001
        log.debug("kite monitor on_tick error for %s: %s", uid, exc)
    return None


async def on_ticks(uid: str, ticks: list, *, client) -> None:
    """Fan a batch of decoded ticks through ``on_tick``."""
    for t in ticks or []:
        try:
            token = int(t.get("instrument_token") or 0)
            ltp = float(t.get("last_price") or 0.0)
        except Exception:
            continue
        if token and ltp:
            await on_tick(uid, token, ltp, client=client)
