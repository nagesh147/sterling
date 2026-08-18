"""Execution adapter for the independent ORB strategy.

The ORB engine produces a BUY-only option trade plan. This module is the strategy's
execution boundary: universal Trading Mode owns Manual/Auto and Paper/Live, while
Kite owns the actual order and protection lifecycle.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

_IST = timezone(timedelta(hours=5, minutes=30))


def _state(uid: str) -> dict[str, Any]:
    from app.services import db
    import json
    key = f"nifty_orb_options_trade_state:{uid}"
    try:
        raw = db.get_config(key)
        state = json.loads(raw) if raw else {}
    except Exception:
        state = {}
    today = datetime.now(_IST).date().isoformat()
    if state.get("date") != today:
        state = {"date": today, "count": 0, "signals": []}
    return state


def _save_state(uid: str, state: dict[str, Any]) -> None:
    from app.services import db
    import json
    db.set_config(
        f"nifty_orb_options_trade_state:{uid}",
        json.dumps(state, separators=(",", ":")),
    )


async def _find_contract(client, symbol: str, underlying: str) -> tuple[str, dict] | tuple[None, None]:
    for exchange in ("NFO", "BFO"):
        try:
            rows = await client.search_instruments(underlying, exchange, limit=10000)
        except Exception:
            continue
        for row in rows:
            if str(row.get("tradingsymbol") or "").upper() == symbol.upper():
                return exchange, row
    return None, None


async def execute_scan(uid: str, *, scan: dict[str, Any], max_trades: int) -> dict[str, Any]:
    """Execute fresh ORB BUY plans through the universal Kite safety path."""
    from app.services.kite_engine import state as engine_state
    from app.services.kite_engine import positions, protection
    from app.services import live_safety
    from app.services.exchanges.kite import accounts

    universal = engine_state.get_config(uid)
    if not getattr(universal, "auto_execute", False):
        return {"status": "advisory", "executed": []}

    account = accounts.get_active(uid)
    if not account:
        return {"status": "blocked", "reason": "No active Kite account", "executed": []}

    trade_state = _state(uid)
    if int(trade_state.get("count", 0)) >= max_trades:
        return {"status": "daily_limit", "executed": [], "count": trade_state["count"]}

    client = await accounts.acquire_client(account)
    executed: list[dict[str, Any]] = []
    seen_underlyings = {
        str(p.underlying).upper()
        for p in positions.open_positions(uid)
        if p.status in (positions.OPEN, positions.PENDING)
    }

    for row in scan.get("signals", []):
        if row.get("status") != "signal":
            continue
        plan = row.get("trade") or {}
        contract = plan.get("contract") or {}
        symbol = str(contract.get("symbol") or "")
        underlying = str(row.get("underlying") or "").upper()
        quantity = int(plan.get("quantity") or 0)
        if not symbol or quantity <= 0 or not underlying:
            continue
        if underlying in seen_underlyings:
            continue
        if len(executed) + int(trade_state.get("count", 0)) >= max_trades:
            break

        signal = row.get("signal") or {}
        signal_key = f"{underlying}:{signal.get('timestamp')}:{signal.get('direction')}:{symbol}"
        if signal_key in set(trade_state.get("signals", [])):
            continue

        expiry = str(contract.get("expiry") or "")[:10]
        if expiry and expiry == datetime.now(_IST).date().isoformat():
            continue

        idem = live_safety.make_idempotency_key(
            uid,
            symbol,
            "BUY",
            quantity,
            int(datetime.now(_IST).timestamp() * 1000),
        )
        decision = live_safety.assert_safe_to_trade(
            positions=[], idempotency_key=idem, check_daily_loss=False,
        )
        if not decision.allowed and decision.code != "duplicate_order":
            continue
        if live_safety.check_idempotency(idem):
            continue

        exchange, instrument = await _find_contract(client, symbol, underlying)
        if not exchange or not instrument:
            continue
        try:
            quote = await client.get_quote([f"{exchange}:{symbol}"])
            q = (quote or {}).get(f"{exchange}:{symbol}", {}) or {}
            entry = float(q.get("last_price") or plan.get("entry_premium") or 0)
            if entry <= 0:
                continue
            order = await client.place_order_option(
                symbol,
                "buy",
                quantity,
                exchange=exchange,
                tag=idem,
            )
        except Exception as exc:
            executed.append({"status": "error", "underlying": underlying, "symbol": symbol, "error": str(exc)})
            continue

        order_id = str((order or {}).get("order_id") or "")
        if not order_id:
            continue
        live_safety.record_idempotency(idem, order_id)

        try:
            armed = await protection.arm_position(
                client,
                uid,
                symbol=symbol,
                exchange=exchange,
                token=int(instrument.get("instrument_token") or 0),
                qty=quantity,
                lot_size=int(contract.get("lot_size") or instrument.get("lot_size") or 1),
                entry_premium=entry,
                stop_premium=float(plan.get("stop_premium") or 0),
                order_id=order_id,
                stop_mode=universal.stop_mode,
                direction="long",
                signal_direction="long" if signal.get("direction") == "LONG" else "short",
                vehicle="otm_options",
                underlying=underlying,
                exit_mode=universal.exit_mode,
                entry_spot=float(plan.get("underlying_entry") or row.get("spot") or 0),
                entry_delta=float(abs(contract.get("delta") or 0.5)),
                strike=float(contract.get("strike") or 0),
                expiry=expiry,
                target_premium=float(plan.get("target_premium") or 0),
            )
            protected = bool(armed.protected)
            protection_note = armed.describe()
        except Exception as exc:
            protected = False
            protection_note = f"arming failed: {exc}"

        trade_state["count"] = int(trade_state.get("count", 0)) + 1
        trade_state.setdefault("signals", []).append(signal_key)
        seen_underlyings.add(underlying)
        executed.append({
            "status": "executed",
            "underlying": underlying,
            "symbol": symbol,
            "quantity": quantity,
            "order_id": order_id,
            "protected": protected,
            "protection": protection_note,
            "plan": plan,
        })

    _save_state(uid, trade_state)
    return {"status": "executed" if executed else "no_trade", "executed": executed, "count": trade_state["count"]}
