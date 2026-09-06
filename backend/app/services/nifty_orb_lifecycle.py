"""ORB process lifecycle: restart recovery, protection disarm, expiry square-off.

Manual and Auto share one signal/ticket. This module does not generate signals.
It keeps live state honest across restarts and exits.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.logging import get_logger

log = get_logger(__name__)
IST = ZoneInfo("Asia/Kolkata")
ORB_VEHICLES = frozenset({"otm_options", "deep_itm_options"})


def ticket_fingerprint(plan: dict[str, Any], signal: dict[str, Any]) -> str:
    """Stable id for the Manual board ticket and the Auto order.

    Manual Buy and Auto execute_scan must resolve to the same fingerprint for the
    same scan row — one signal, one ticket, two ways to place it.
    """
    contract = plan.get("contract") or {}
    return "|".join(
        [
            str(signal.get("direction") or ""),
            str(signal.get("timestamp") or ""),
            str(contract.get("symbol") or ""),
            str(contract.get("option_type") or ""),
            str(contract.get("strike") or ""),
            str(contract.get("expiry") or "")[:10],
            str(plan.get("quantity") or ""),
            str(plan.get("stop_premium") or ""),
            str(plan.get("target_premium") or ""),
        ]
    )


def manual_mode_response() -> dict[str, Any]:
    """Auto is off: show signals only; user places the same ticket."""
    return {
        "status": "manual",
        "mode": "signals_only",
        "message": "Auto off — board shows the trade ticket; place Buy yourself. Same signal Auto would trade.",
        "executed": [],
    }


def orb_open_positions(uid: str) -> list:
    from app.services.kite_engine import positions

    out = []
    for p in positions.open_positions(uid):
        vehicle = str(getattr(p, "vehicle", "") or "")
        if vehicle in ORB_VEHICLES or vehicle == "":
            # Empty vehicle kept for legacy rows; callers may still filter further.
            out.append(p)
    return out


def recover_trade_state(uid: str) -> dict[str, Any]:
    """Rebuild ORB day-count state after a process restart.

    Positions already rehydrate from ``kite_engine_positions_{uid}``. This syncs
    the ORB trade-state date/count so Auto cannot double-fire past max_trades_per_day
    when the in-memory runner restarts mid-session.
    """
    from app.services.nifty_orb_execution import _save_state, _state

    state = _state(uid)
    open_orb = [
        p
        for p in orb_open_positions(uid)
        if str(getattr(p, "vehicle", "") or "") in ORB_VEHICLES
        or str(getattr(p, "order_id", "") or "").startswith("ORB")
        or "ORB" in str(getattr(p, "guard_key", "") or "")
    ]
    # Day count is fills today, not currently open — never raise the cap from open qty.
    # Only ensure date bucket exists and open underlyings are visible to the next scan.
    underlyings = sorted(
        {str(getattr(p, "underlying", "") or "").upper() for p in open_orb if getattr(p, "underlying", "")}
    )
    state["recovered_open"] = [
        {
            "symbol": p.symbol,
            "underlying": getattr(p, "underlying", ""),
            "qty": int(p.qty or 0),
            "status": p.status,
            "expiry": getattr(p, "expiry", ""),
            "gtt_id": int(getattr(p, "gtt_id", 0) or 0),
        }
        for p in open_orb
    ]
    state["recovered_underlyings"] = underlyings
    _save_state(uid, state)
    return {
        "status": "recovered",
        "date": state.get("date"),
        "count": int(state.get("count", 0)),
        "open_orb": len(open_orb),
        "underlyings": underlyings,
    }


async def resubscribe_protection(uid: str) -> dict[str, Any]:
    """Re-attach tick subscriptions for open ORB positions after restart."""
    from app.services.exchanges.kite import constants as K
    from app.services.exchanges.kite import ticker_manager

    tokens = [int(p.token) for p in orb_open_positions(uid) if int(getattr(p, "token", 0) or 0)]
    if not tokens:
        return {"status": "nothing_to_subscribe", "tokens": []}
    try:
        await ticker_manager.subscribe(uid, tokens, mode=K.MODE_LTP)
        return {"status": "subscribed", "tokens": tokens}
    except Exception as exc:  # noqa: BLE001
        log.warning("ORB resubscribe failed for %s: %s", uid, exc)
        return {"status": "subscribe_failed", "tokens": tokens, "error": str(exc)}


async def recover_after_restart(uid: str) -> dict[str, Any]:
    """Full restart recovery for one user — call once when the ORB runner starts."""
    trade = recover_trade_state(uid)
    ticks = await resubscribe_protection(uid)
    return {"trade_state": trade, "ticks": ticks}


async def disarm_position(client, uid: str, *, symbol: str, reason: str = "disarmed") -> dict[str, Any]:
    """Tear down protection for a held ORB contract, then mark the registry closed.

    Cancels the broker GTT when present, best-effort unsubscribes the tick token,
    and closes the positions registry row. Does not place a market exit — callers
    that need flat inventory must sell first (see square_off_expired).
    """
    from app.services.kite_engine import positions, protective_stop, state
    from app.services.kite_engine.protection import disarm_position as _disarm

    return await _disarm(client, uid, symbol=symbol, reason=reason)


async def square_off_expired(client, uid: str, *, today: datetime | None = None) -> dict[str, Any]:
    """Market-sell ORB option positions whose expiry is today or earlier (IST)."""
    from app.services.kite_engine import positions, state
    from app.services.kite_engine.protection import disarm_position as _disarm
    from app.services.nifty_orb_execution import _sell_and_verify

    now = today or datetime.now(IST)
    session = now.astimezone(IST).date()
    closed: list[dict[str, Any]] = []
    for p in list(orb_open_positions(uid)):
        expiry_s = str(getattr(p, "expiry", "") or "")[:10]
        if not expiry_s:
            continue
        try:
            expiry = datetime.strptime(expiry_s, "%Y-%m-%d").date()
        except ValueError:
            continue
        if expiry > session:
            continue
        qty = int(p.qty or 0)
        ok, note = await _sell_and_verify(client, p.symbol, p.exchange, qty)
        disarm = await _disarm(client, uid, symbol=p.symbol, reason=f"expiry_square_off:{expiry_s}")
        if ok:
            positions.close(uid, p.symbol, reason=f"expiry_square_off:{expiry_s}")
            state.log(uid, "info", f"ORB expiry square-off {p.symbol}: {note}")
        else:
            state.log(uid, "order_failed", f"ORB expiry square-off FAILED {p.symbol}: {note}")
        closed.append(
            {
                "symbol": p.symbol,
                "expiry": expiry_s,
                "sold": ok,
                "note": note,
                "disarm": disarm,
            }
        )
    return {"status": "ok", "squared": closed}
