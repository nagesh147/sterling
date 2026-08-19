"""Fail-closed execution adapter for the NIFTY ORB option-buying strategy.

The scanner produces a plan, but a live order is never trusted merely because the
plan was valid a few seconds earlier. Execution re-validates the contract, quote,
spread, expiry and conservative worst-case premium risk immediately before entry.
Protection is mandatory: a filled position that cannot be protected is immediately
closed (or the global kill switch is asserted if the emergency close also fails).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

_IST = timezone(timedelta(hours=5, minutes=30))
_MAX_QUOTE_AGE_S = 5.0


def _state(uid: str) -> dict[str, Any]:
    from app.services import db
    import json
    try:
        raw = db.get_config(f"nifty_orb_options_trade_state:{uid}")
        state = json.loads(raw) if raw else {}
    except Exception:
        state = {}
    today = datetime.now(_IST).date().isoformat()
    if state.get("date") != today:
        state = {"date": today, "count": 0, "signals": []}
    state.setdefault("signals", [])
    return state


def _save_state(uid: str, state: dict[str, Any]) -> None:
    from app.services import db
    import json
    db.set_config(f"nifty_orb_options_trade_state:{uid}", json.dumps(state, separators=(",", ":")))


async def _find_contract(client, symbol: str, underlying: str) -> tuple[str | None, dict | None]:
    for exchange in ("NFO", "BFO"):
        try:
            rows = await client.search_instruments(underlying, exchange, limit=10000)
        except Exception:
            continue
        for row in rows or []:
            if str(row.get("tradingsymbol") or "").upper() == symbol.upper():
                return exchange, row
    return None, None


async def _existing_order_by_tag(client, tag: str) -> tuple[bool, dict | None]:
    """Return (query_succeeded, matching_order).

    A broker query failure is not equivalent to 'no order'. Treating it as no order
    can submit a duplicate after a network timeout.
    """
    try:
        orders = await client.get_orders()
    except Exception:
        return False, None
    return True, next((o for o in orders or [] if str(o.get("tag") or "") == tag), None)


async def _resolve_fill(client, order_id: str, *, timeout_s: float = 5.0) -> tuple[int, float, str]:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        latest: dict[str, Any] = {}
        try:
            history = await client.get_order_history(order_id)
            latest = history[-1] if isinstance(history, list) and history else (history if isinstance(history, dict) else {})
        except Exception:
            pass
        status = str(latest.get("status") or "").upper()
        filled = int(float(latest.get("filled_quantity") or latest.get("filled_qty") or 0))
        avg = float(latest.get("average_price") or latest.get("average_price_filled") or 0)
        if not filled:
            try:
                trades = await client.get_order_trades(order_id)
                if trades:
                    filled = sum(int(float(t.get("quantity") or 0)) for t in trades)
                    value = sum(float(t.get("quantity") or 0) * float(t.get("average_price") or t.get("price") or 0) for t in trades)
                    avg = value / filled if filled else avg
            except Exception:
                pass
        if status in {"COMPLETE", "PARTIALLY FILLED", "PARTIAL", "CANCELLED", "REJECTED"} or filled > 0:
            return filled, avg, status
        if asyncio.get_running_loop().time() >= deadline:
            return filled, avg, status or "UNKNOWN"
        await asyncio.sleep(0.25)


async def _cancel_unfilled_remainder(client, order_id: str) -> bool:
    try:
        await client.cancel_order(order_id)
        return True
    except Exception:
        return False


async def _emergency_close(client, *, symbol: str, exchange: str, quantity: int) -> bool:
    """Best-effort immediate exit used when protection cannot be armed."""
    if quantity <= 0:
        return True
    try:
        result = await client.place_order_option(symbol, "sell", quantity, exchange=exchange, tag="ORB-PROTECTION-FAIL-CLOSE")
        return bool((result or {}).get("order_id") or (result or {}).get("orderId"))
    except Exception:
        return False


async def _fresh_quote(client, *, exchange: str, symbol: str) -> dict[str, Any]:
    key = f"{exchange}:{symbol}"
    payload = await client.get_quote([key])
    quote = (payload or {}).get(key)
    if not quote:
        raise RuntimeError("live option quote unavailable")
    depth = quote.get("depth") or {}
    buys = depth.get("buy") or []
    sells = depth.get("sell") or []
    bid = float((buys[0] if buys else {}).get("price") or 0)
    ask = float((sells[0] if sells else {}).get("price") or 0)
    ltp = float(quote.get("last_price") or 0)
    if ask <= 0 or bid <= 0 or ask < bid or ltp <= 0:
        raise RuntimeError("option quote is not executable")
    mid = (bid + ask) / 2.0
    spread_pct = (ask - bid) / mid * 100.0 if mid > 0 else float("inf")
    if spread_pct > 1.5:
        raise RuntimeError(f"live option spread {spread_pct:.2f}% exceeds 1.50% execution ceiling")
    return {
        "bid": bid,
        "ask": ask,
        "ltp": ltp,
        "spread_pct": spread_pct,
        "volume": float(quote.get("volume") or 0),
        "oi": float(quote.get("oi") or 0),
        "timestamp": quote.get("timestamp") or quote.get("last_trade_time"),
    }


def _conservative_quantity(*, requested: int, lot_size: int, ask: float, max_risk_inr: float) -> int:
    """Size against the full premium, not the modelled delta stop.

    An option can gap through a server-side stop. Treating the premium as the
    conservative loss ceiling prevents the strategy from sizing based on a
    protection assumption that may fail during a fast market.
    """
    if requested <= 0 or lot_size <= 0 or ask <= 0 or max_risk_inr <= 0:
        return 0
    max_lots = int(max_risk_inr // (ask * lot_size))
    return min(requested, max_lots * lot_size)


async def execute_scan(uid: str, *, scan: dict[str, Any], max_trades: int) -> dict[str, Any]:
    """Execute scanner-produced BUY plans with fail-closed live safeguards."""
    from app.services.kite_engine import state as engine_state, positions, protection
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
        requested_quantity = int(plan.get("quantity") or 0)
        if not symbol or requested_quantity <= 0 or not underlying or underlying in seen_underlyings:
            continue
        if len(executed) + int(trade_state.get("count", 0)) >= max_trades:
            break

        signal = row.get("signal") or {}
        direction = str(signal.get("direction") or "")
        expected_type = "CE" if direction == "LONG" else "PE" if direction == "SHORT" else ""
        if expected_type != str(contract.get("option_type") or ""):
            executed.append({"status": "blocked", "underlying": underlying, "symbol": symbol, "reason": "option direction mismatch"})
            continue

        signal_key = f"{underlying}:{signal.get('timestamp')}:{direction}:{symbol}"
        if signal_key in set(trade_state.get("signals", [])):
            continue
        idem = live_safety.make_idempotency_key(uid, signal_key, "BUY")

        decision = live_safety.assert_safe_to_trade(
            positions=positions.open_positions(uid),
            idempotency_key=idem,
            check_daily_loss=False,
        )
        if not decision.allowed and decision.code != "duplicate_order":
            executed.append({"status": "blocked", "underlying": underlying, "symbol": symbol, "reason": decision.reason})
            continue
        if live_safety.check_idempotency(idem):
            continue

        exchange, instrument = await _find_contract(client, symbol, underlying)
        if not exchange or not instrument:
            executed.append({"status": "blocked", "underlying": underlying, "symbol": symbol, "reason": "contract no longer exists"})
            continue

        # Revalidate expiry and contract identity at the exact execution point.
        try:
            expiry = datetime.strptime(str(instrument.get("expiry"))[:10], "%Y-%m-%d").date()
            dte = (expiry - datetime.now(_IST).date()).days
        except (TypeError, ValueError):
            executed.append({"status": "blocked", "underlying": underlying, "symbol": symbol, "reason": "invalid contract expiry"})
            continue
        if dte < 0:
            executed.append({"status": "blocked", "underlying": underlying, "symbol": symbol, "reason": "expired contract"})
            continue

        # Never trust the scanner's cached premium. Obtain a fresh broker quote and
        # size from the full premium as the conservative worst-case loss ceiling.
        try:
            quote = await _fresh_quote(client, exchange=exchange, symbol=symbol)
        except Exception as exc:
            executed.append({"status": "blocked", "underlying": underlying, "symbol": symbol, "reason": f"quote validation failed: {exc}"})
            continue

        lot_size = int(contract.get("lot_size") or instrument.get("lot_size") or 1)
        max_risk = float(getattr(getattr(universal, "risk_params", None), "max_risk_inr", 0) or 0)
        if max_risk <= 0:
            # ORB's persisted strategy risk budget is the authoritative fallback.
            try:
                from app.services.nifty_orb_options import get_config
                max_risk = float(get_config().max_risk_inr)
            except Exception:
                max_risk = 0.0
        quantity = _conservative_quantity(
            requested=requested_quantity,
            lot_size=lot_size,
            ask=quote["ask"],
            max_risk_inr=max_risk,
        )
        if quantity <= 0:
            executed.append({"status": "blocked", "underlying": underlying, "symbol": symbol, "reason": "one option lot exceeds conservative premium risk budget"})
            continue

        # Re-check the universal safety gate immediately before submission.
        decision = live_safety.assert_safe_to_trade(
            positions=positions.open_positions(uid),
            idempotency_key=idem,
            check_daily_loss=False,
        )
        if not decision.allowed:
            executed.append({"status": "blocked", "underlying": underlying, "symbol": symbol, "reason": decision.reason})
            continue

        existing_ok, existing = await _existing_order_by_tag(client, idem)
        if not existing_ok:
            executed.append({"status": "blocked", "underlying": underlying, "symbol": symbol, "reason": "cannot establish broker order state; refusing duplicate-risk submission"})
            continue
        if existing:
            order_id = str(existing.get("order_id") or existing.get("orderId") or "")
        else:
            try:
                order = await client.place_order_option(symbol, "buy", quantity, exchange=exchange, tag=idem)
            except Exception as exc:
                executed.append({"status": "error", "underlying": underlying, "symbol": symbol, "error": str(exc)})
                continue
            order_id = str((order or {}).get("order_id") or (order or {}).get("orderId") or "")
            if not order_id:
                # Unknown broker outcome: do not retry blindly. Kill further ORB
                # entries until the account can be reconciled manually.
                live_safety.set_kill_switch(True, "ORB order submission returned no order id; reconcile broker state")
                executed.append({"status": "blocked", "underlying": underlying, "symbol": symbol, "reason": "unknown broker order outcome; kill switch asserted"})
                continue
            live_safety.record_idempotency(idem, order_id)

        filled_qty, fill_price, broker_status = await _resolve_fill(client, order_id)
        if filled_qty <= 0:
            if broker_status not in {"CANCELLED", "REJECTED"}:
                if not await _cancel_unfilled_remainder(client, order_id):
                    live_safety.set_kill_switch(True, "ORB unfilled order could not be cancelled; reconcile broker state")
            executed.append({"status": "pending_or_unfilled", "underlying": underlying, "symbol": symbol, "order_id": order_id, "broker_status": broker_status})
            continue

        if filled_qty < quantity and not await _cancel_unfilled_remainder(client, order_id):
            live_safety.set_kill_switch(True, "ORB partial-fill remainder could not be cancelled; reconcile broker state")

        try:
            armed = await protection.arm_position(
                client, uid,
                symbol=symbol,
                exchange=exchange,
                token=int(instrument.get("instrument_token") or 0),
                qty=filled_qty,
                lot_size=lot_size,
                entry_premium=fill_price or quote["ask"],
                stop_premium=float(plan.get("stop_premium") or 0),
                order_id=order_id,
                stop_mode=universal.stop_mode,
                direction="long",
                signal_direction="long" if direction == "LONG" else "short",
                vehicle="otm_options",
                underlying=underlying,
                exit_mode=universal.exit_mode,
                entry_spot=float(plan.get("underlying_entry") or row.get("spot") or 0),
                entry_delta=float(abs(contract.get("delta") or 0.5)),
                strike=float(contract.get("strike") or 0),
                expiry=str(contract.get("expiry") or "")[:10],
                target_premium=float(plan.get("target_premium") or 0),
            )
            if not armed.protected:
                raise RuntimeError(armed.describe())
        except Exception as exc:
            closed = await _emergency_close(client, symbol=symbol, exchange=exchange, quantity=filled_qty)
            if not closed:
                live_safety.set_kill_switch(True, f"ORB position {symbol} is unprotected and emergency close failed")
                executed.append({"status": "critical_unprotected", "underlying": underlying, "symbol": symbol, "order_id": order_id, "quantity": filled_qty, "reason": str(exc)})
            else:
                executed.append({"status": "protected_entry_failed_closed", "underlying": underlying, "symbol": symbol, "order_id": order_id, "quantity": filled_qty, "reason": str(exc)})
            continue

        trade_state["count"] = int(trade_state.get("count", 0)) + 1
        trade_state.setdefault("signals", []).append(signal_key)
        seen_underlyings.add(underlying)
        executed.append({
            "status": "executed",
            "underlying": underlying,
            "symbol": symbol,
            "quantity": filled_qty,
            "requested_quantity": quantity,
            "fill_price": fill_price,
            "broker_status": broker_status,
            "order_id": order_id,
            "protected": True,
            "protection": armed.describe(),
            "conservative_max_loss_inr": round(quote["ask"] * filled_qty, 2),
            "plan": plan,
        })

    _save_state(uid, trade_state)
    return {"status": "executed" if executed else "no_trade", "executed": executed, "count": trade_state["count"]}
