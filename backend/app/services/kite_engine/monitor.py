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

# (uid, symbol) whose market exit order is mid-flight. The exit paths — the WS tick
# monitor (on_tick) and the scan loop (_square_off_expiring / _time_stop_positions) —
# are separate coroutines on one event loop and each calls _exit_position, which
# awaits the SELL placement BEFORE it marks the position closed. This set is claimed
# synchronously (no await between the check and the add, so it is race-free on the
# single-threaded loop) so a second exit path for the same position bails instead of
# placing a duplicate SELL (the double-sell / naked-short bug).
_exiting: set = set()


def _record_realized(uid: str, p: "pos.OpenPosition", exit_price: float) -> None:
    """Book a closed position's realized PnL (INR) into the per-day accumulator that
    backs the INR daily-loss breaker. Long: (exit − entry)·qty; short future: negated.
    Uses the confirmed fill price when known, else the intended entry premium."""
    entry = float(p.fill_price or p.entry_premium or 0.0)
    if entry <= 0 or not exit_price or p.qty <= 0:
        return
    sign = 1.0 if p.direction == "long" else -1.0
    state.record_realized_pnl(uid, (float(exit_price) - entry) * p.qty * sign)


async def on_order_update(uid: str, order: dict, *, client=None) -> None:
    """Handle one Kite order postback for ``uid`` (workstream E).

    Matches the postback to a registered position by tradingsymbol, then classifies
    it by order_id + transaction_type so the ENTRY fill and a PROTECTIVE-EXIT fill
    are never confused:

      * ENTRY (order_id matches the entry, or a legacy postback with no id) → confirm
        the fill price / status, or mark rejected and release the guard.
      * EXIT  (a COMPLETE on the position's exit side — SELL for a long, BUY to cover
        a short — from a *different* order id) → a broker GTT / protective stop fired
        at Zerodha. Reconcile our registry to CLOSED and release the guard, so the tick
        monitor does not later market-SELL the same position AGAIN (the double-sell /
        naked-short bug). Best-effort token unsubscribe.

    Unknown orders (manual trades, other strategies) are ignored. Never raises — a bad
    postback must not kill the WS loop.
    """
    try:
        symbol = str(order.get("tradingsymbol", "")).strip()
        if not symbol:
            return
        p = pos.get(uid, symbol)
        if p is None:
            return  # not one of ours
        status = str(order.get("status", "")).upper()
        txn = str(order.get("transaction_type", "")).upper()
        oid = str(order.get("order_id", "")).strip()
        exit_side = "SELL" if p.direction == "long" else "BUY"  # side that CLOSES us
        is_entry = bool(oid) and oid == str(p.order_id)

        # ── protective/GTT exit already filled at the broker → reconcile ──────
        # Only when the position is still live (pending/open). If it is already CLOSED
        # the monitor's OWN _exit_position placed and recorded this SELL — its COMPLETE
        # postback must NOT re-enter here and book realized PnL a second time (which
        # would trip the INR daily-loss breaker at ~half the configured limit).
        if (status == _FILLED_STATUS and txn == exit_side and not is_entry
                and p.status in (pos.PENDING, pos.OPEN)):
            avg = float(order.get("average_price") or 0.0)
            pos.close(uid, symbol,
                      reason=(f"broker stop/exit fill @ ₹{avg:.2f}" if avg else "broker stop/exit fill"))
            _record_realized(uid, p, avg)
            if p.guard_key:
                state.clear_auto_open(uid, p.guard_key)
            if p.token:
                try:
                    from app.services.exchanges.kite import ticker_manager
                    await ticker_manager.unsubscribe(uid, [p.token])
                except Exception as _exc:  # noqa: BLE001
                    log.debug("suppressed: %s", _exc)
            state.log(uid, "order_placed",
                      f"{symbol} exit filled at broker @ ₹{avg:.2f} — position reconciled closed")
            return

        if status == _FILLED_STATUS and (is_entry or not oid):
            avg = float(order.get("average_price") or 0.0)
            pos.mark_filled(uid, symbol, avg)
            state.log(uid, "info",
                      f"Fill confirmed: {symbol} @ ₹{avg:.2f} (#{oid})")
        elif status in _DEAD_STATUSES and (is_entry or not oid):
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
    # Claim the exit synchronously (single-threaded loop → check-then-add is atomic):
    # if another exit path already holds this claim, or the position is no longer live,
    # bail without placing a duplicate SELL. The claim is released on placement failure
    # so a genuine retry can proceed; on success the position ends CLOSED and the status
    # check keeps any later exit out.
    key = (uid, p.symbol)
    if key in _exiting or p.status not in (pos.OPEN, pos.PENDING):
        return
    _exiting.add(key)
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
        _exiting.discard(key)
        state.log(uid, "order_failed", f"Trail exit {exit_side.upper()} {p.symbol} failed: {exc}")
        return
    if p.gtt_id:
        await pstop.cancel_stop(client, p.gtt_id)
    breach_dir = "≥" if p.direction == "short" else "≤"
    close_reason = reason or f"trail breach @ ₹{ltp:.2f} {breach_dir} ₹{p.stop_premium:.2f}"
    pos.close(uid, p.symbol, reason=close_reason)
    _exiting.discard(key)  # closed now; status guard keeps later exits out
    _record_realized(uid, p, ltp)
    if p.guard_key:
        state.clear_auto_open(uid, p.guard_key)
    state.log(uid, "order_placed",
              f"{exit_side.upper()} {p.qty} {p.symbol} @ market — {close_reason}")
    # Unsubscribe the token now that we no longer hold this position.
    if p.token:
        try:
            from app.services.exchanges.kite import ticker_manager
            await ticker_manager.unsubscribe(uid, [p.token])
        except Exception as _exc:# noqa: BLE001
            log.debug("suppressed: %s", _exc)


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
