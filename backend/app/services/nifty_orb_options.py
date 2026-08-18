"""Runtime orchestration for the NIFTY ORB + VWAP options strategy.

The underlying generates the signal. Options are the execution vehicle.
Market data can come from Kite or TrueData; execution remains Kite.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.engines.nifty_orb_options import (
    Bar, OptionContract, StrategyConfig, build_trade_plan, generate_signal,
    select_option, summarize_pnl,
)
from app.core.config import settings

_IST = timezone(timedelta(hours=5, minutes=30))
_CONFIG_KEY = "nifty_orb_options_config"


def _default() -> StrategyConfig:
    return StrategyConfig()


def get_config() -> StrategyConfig:
    try:
        from app.services import db
        raw = db.get_config(_CONFIG_KEY)
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            allowed = set(StrategyConfig.__dataclass_fields__)
            return StrategyConfig(**{k: v for k, v in {**_default().__dict__, **data}.items() if k in allowed})
    except Exception:
        pass
    return _default()


def set_config(values: dict[str, Any]) -> StrategyConfig:
    current = get_config().__dict__.copy()
    unknown = sorted(set(values) - set(current))
    if unknown:
        raise ValueError(f"Unknown NIFTY ORB config fields: {', '.join(unknown)}")
    current.update(values)
    if current["data_source"] not in {"kite", "truedata"}:
        raise ValueError("data_source must be 'kite' or 'truedata'")
    if current["execution_broker"] != "kite":
        raise ValueError("execution_broker is fixed to 'kite'")
    if current["interval_minutes"] not in {1, 3, 5, 10, 15}:
        raise ValueError("interval_minutes must be one of 1, 3, 5, 10, 15")
    if current["opening_range_minutes"] not in {5, 10, 15, 20, 30}:
        raise ValueError("opening_range_minutes must be one of 5, 10, 15, 20, 30")
    if current["max_trades_per_day"] < 1:
        raise ValueError("max_trades_per_day must be >= 1")
    if current["max_risk_inr"] <= 0:
        raise ValueError("max_risk_inr must be > 0")
    cfg = StrategyConfig(**current)
    from app.services import db
    db.set_config(_CONFIG_KEY, json.dumps(cfg.__dict__, separators=(",", ":")))
    return cfg


def _bar_from_any(row: Any) -> Bar:
    ts = row.get("timestamp") or row.get("time") or row.get("timestamp_ms")
    if isinstance(ts, (int, float)):
        timestamp = datetime.fromtimestamp(float(ts) / 1000.0, tz=_IST)
    elif isinstance(ts, datetime):
        timestamp = ts if ts.tzinfo else ts.replace(tzinfo=_IST)
    else:
        text = str(ts).replace("Z", "+00:00")
        timestamp = datetime.fromisoformat(text) if "+" in text[10:] else datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_IST)
    return Bar(timestamp=timestamp, open=float(row["open"]), high=float(row["high"]), low=float(row["low"]), close=float(row["close"]), volume=float(row.get("volume") or 0.0))


def normalize_option_chain(rows: Any, expiry: str | None = None) -> list[OptionContract]:
    if isinstance(rows, dict):
        rows = rows.get("Records") or rows.get("records") or rows.get("data") or rows.get("options") or []
    out: list[OptionContract] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        typ = str(row.get("option_type") or row.get("type") or row.get("opttype") or "").upper()
        typ = {"CALL": "CE", "C": "CE", "PUT": "PE", "P": "PE"}.get(typ, typ)
        if typ not in {"CE", "PE"}:
            continue
        try:
            strike = float(row.get("strike") or row.get("strike_price"))
        except (TypeError, ValueError):
            continue
        exp = str(row.get("expiry") or row.get("expiry_date") or expiry or "")[:10]
        symbol = str(row.get("symbol") or row.get("tradingsymbol") or row.get("instrument") or "")
        out.append(OptionContract(
            symbol=symbol, strike=strike, expiry=exp, option_type=typ,
            ltp=float(row.get("ltp") or row.get("last_price") or row.get("close") or 0),
            bid=float(row.get("bid") or row.get("bid_price") or 0),
            ask=float(row.get("ask") or row.get("ask_price") or 0),
            lot_size=int(row.get("lot_size") or row.get("lotsize") or 75),
            delta=float(row["delta"]) if row.get("delta") not in (None, "") else None,
            volume=float(row.get("volume") or 0),
            open_interest=float(row.get("oi") or row.get("open_interest") or 0),
        ))
    return out


async def _kite_bars(user_id: str, interval: str, limit: int = 240) -> list[Bar]:
    from app.services.exchanges.kite import accounts as kite_accounts
    from app.services.exchanges import instrument_registry as registry
    acct = kite_accounts.get_active(user_id)
    if not acct:
        raise RuntimeError("No active Kite account")
    client = await kite_accounts.acquire_client(acct)
    inst = registry.get_instrument("NIFTY") or registry.get_instrument("NIFTY 50")
    if not inst:
        raise RuntimeError("NIFTY instrument is not registered")
    rows = await client.get_candles(inst, interval, limit=limit)
    return [_bar_from_any({"timestamp_ms": r.timestamp_ms, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume}) for r in rows]


async def _kite_spot_and_options(user_id: str, direction: str) -> tuple[float, list[OptionContract]]:
    from app.services.exchanges.kite import accounts as kite_accounts
    acct = kite_accounts.get_active(user_id)
    if not acct:
        raise RuntimeError("No active Kite account")
    client = await kite_accounts.acquire_client(acct)
    quote = await client.get_ltp(["NSE:NIFTY 50"])
    spot = float((quote.get("NSE:NIFTY 50") or {}).get("last_price") or 0)
    instruments = await client.search_instruments("NIFTY", "NFO", limit=5000)
    today = datetime.now(_IST).date()
    candidates: list[tuple[Any, dict]] = []
    for row in instruments:
        if str(row.get("name") or "").upper() != "NIFTY":
            continue
        typ = str(row.get("instrument_type") or "").upper()
        wanted = "CE" if direction == "LONG" else "PE"
        if typ != wanted:
            continue
        try:
            exp = datetime.strptime(str(row.get("expiry"))[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if exp >= today:
            candidates.append((exp, row))
    if not candidates:
        raise RuntimeError("No NIFTY option contracts available")
    nearest = min(exp for exp, _ in candidates)
    contracts: list[OptionContract] = []
    for exp, row in candidates:
        if exp != nearest:
            continue
        symbol = str(row.get("tradingsymbol") or "")
        try:
            quote_data = await client.get_quote([f"NFO:{symbol}"])
            data = quote_data.get(f"NFO:{symbol}", {}) or {}
            depth = data.get("depth") or {}
            buy = (depth.get("buy") or [{}])[0]
            sell = (depth.get("sell") or [{}])[0]
            contracts.append(OptionContract(
                symbol=symbol, strike=float(row.get("strike") or 0), expiry=exp.isoformat(),
                option_type=str(row.get("instrument_type")), ltp=float(data.get("last_price") or 0),
                bid=float(buy.get("price") or 0), ask=float(sell.get("price") or 0),
                lot_size=int(row.get("lot_size") or 1), volume=float(data.get("volume") or 0),
                open_interest=float(data.get("oi") or 0),
            ))
        except Exception:
            continue
    return spot, contracts


async def snapshot(user_id: str) -> dict[str, Any]:
    cfg = get_config()
    if not cfg.enabled:
        return {"enabled": False, "signal": None, "plan": None, "data_source": cfg.data_source}
    if cfg.data_source == "kite":
        bars = await _kite_bars(user_id, f"{cfg.interval_minutes}m")
        signal = generate_signal(bars, cfg)
        spot = bars[-1].close
        contracts: list[OptionContract] = []
        if signal.direction != "NONE":
            spot, contracts = await _kite_spot_and_options(user_id, signal.direction)
    else:
        from app.services.market_data.truedata import TrueDataHistoricalClient
        client = TrueDataHistoricalClient(settings.truedata_username, settings.truedata_password, timeout=settings.truedata_timeout_seconds)
        try:
            raw = await client.get_last_bars("NIFTY 50", 240, interval=f"{cfg.interval_minutes}min")
            bars = [_bar_from_any(row) for row in raw]
            signal = generate_signal(bars, cfg)
            spot = bars[-1].close
            contracts = []
            if signal.direction != "NONE":
                contracts = normalize_option_chain(await client.get_option_chain("NIFTY", "nearest"))
        finally:
            await client.aclose()
    plan = None
    if signal.direction != "NONE":
        option = select_option(spot, signal.direction, contracts, cfg)
        plan = build_trade_plan(signal, option, cfg, spot=spot)
    return {"enabled": True, "data_source": cfg.data_source, "execution_broker": cfg.execution_broker, "signal": signal.to_dict(), "plan": plan.to_dict() if plan else None}


def backtest_from_bars(rows: list[dict[str, Any]], cfg: StrategyConfig | None = None) -> dict[str, Any]:
    cfg = cfg or get_config()
    bars = [_bar_from_any(row) for row in rows]
    if len(bars) < 100:
        return {"metrics": summarize_pnl([]), "warning": "At least 100 bars are required"}
    pnls: list[float] = []
    current_day = None
    day_trades = 0
    for i in range(60, len(bars)):
        day = bars[i].timestamp.date()
        if day != current_day:
            current_day, day_trades = day, 0
        if day_trades >= cfg.max_trades_per_day:
            continue
        signal = generate_signal(bars[:i + 1], cfg)
        if signal.direction == "NONE":
            continue
        entry = bars[i].close
        risk = signal.atr * cfg.stop_buffer_atr
        if risk <= 0:
            continue
        stop = entry - risk if signal.direction == "LONG" else entry + risk
        target = entry + risk * cfg.target_r if signal.direction == "LONG" else entry - risk * cfg.target_r
        outcome = None
        for bar in bars[i + 1:]:
            if bar.timestamp.date() != day:
                break
            if signal.direction == "LONG":
                if bar.low <= stop:
                    outcome = -risk
                    break
                if bar.high >= target:
                    outcome = target - entry
                    break
            else:
                if bar.high >= stop:
                    outcome = -risk
                    break
                if bar.low <= target:
                    outcome = entry - target
                    break
        if outcome is not None:
            pnls.append(outcome)
            day_trades += 1
    metrics = summarize_pnl(pnls)
    metrics.update({"model": "underlying-point baseline", "costs_included": False, "option_pnl": False})
    return {"metrics": metrics, "warning": "Underlying baseline only. Option-level replay requires historical option premiums, contracts, costs and slippage."}
