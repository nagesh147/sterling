"""Runtime orchestration for the NIFTY ORB options strategy.

Market-data source is selectable between Zerodha Kite and TrueData. Execution is
kept on the existing Kite order/protection path so a data-source switch cannot
silently change the execution broker.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.engines.nifty_orb_options import Bar, OptionContract, Signal, StrategyConfig, TradePlan, build_trade_plan, generate_signal, select_option, summarize_pnl
from app.core.config import settings

_IST = timezone(timedelta(hours=5, minutes=30))

_DEFAULTS = StrategyConfig()
_CONFIG = StrategyConfig()


def get_config() -> StrategyConfig:
    return _CONFIG


def set_config(values: dict[str, Any]) -> StrategyConfig:
    global _CONFIG
    current = _CONFIG.__dict__.copy()
    current.update(values)
    # Defensive normalization: reject unknown keys and unsafe execution defaults.
    unknown = sorted(set(current) - set(StrategyConfig.__dataclass_fields__))
    if unknown:
        raise ValueError(f"Unknown NIFTY ORB config fields: {', '.join(unknown)}")
    if current["data_source"] not in {"kite", "truedata"}:
        raise ValueError("data_source must be 'kite' or 'truedata'")
    if current["execution_broker"] != "kite":
        raise ValueError("execution_broker is fixed to 'kite' for this strategy")
    if current["interval_minutes"] not in {1, 3, 5, 10, 15}:
        raise ValueError("interval_minutes must be one of 1, 3, 5, 10, 15")
    if current["opening_range_minutes"] not in {5, 10, 15, 20, 30}:
        raise ValueError("opening_range_minutes must be one of 5, 10, 15, 20, 30")
    if current["max_trades_per_day"] < 1:
        raise ValueError("max_trades_per_day must be >= 1")
    _CONFIG = StrategyConfig(**current)
    return _CONFIG


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


def normalize_truedata_option_chain(payload: Any, expiry: str | None = None) -> list[OptionContract]:
    """Normalize common TrueData option-chain response shapes.

    TrueData deployments expose either a list of rows or a Records/data wrapper;
    field aliases are intentionally accepted so the strategy boundary is stable.
    """
    if isinstance(payload, dict):
        rows = payload.get("Records") or payload.get("records") or payload.get("data") or payload.get("options") or []
    else:
        rows = payload
    if isinstance(rows, dict):
        rows = rows.get("Records") or rows.get("data") or []
    out: list[OptionContract] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        typ = str(r.get("option_type") or r.get("type") or r.get("opttype") or "").upper()
        if typ in {"CALL", "C"}: typ = "CE"
        if typ in {"PUT", "P"}: typ = "PE"
        if typ not in {"CE", "PE"}: continue
        exp = str(r.get("expiry") or r.get("expiry_date") or expiry or "")[:10]
        symbol = str(r.get("symbol") or r.get("tradingsymbol") or r.get("instrument") or r.get("symbolid") or "")
        try:
            strike = float(r.get("strike") or r.get("strike_price"))
            ltp = float(r.get("ltp") or r.get("last_price") or r.get("close") or 0)
        except (TypeError, ValueError):
            continue
        out.append(OptionContract(
            symbol=symbol,
            strike=strike,
            expiry=exp,
            option_type=typ,
            ltp=ltp,
            bid=float(r.get("bid") or r.get("bid_price") or 0),
            ask=float(r.get("ask") or r.get("ask_price") or 0),
            lot_size=int(r.get("lot_size") or r.get("lotsize") or 75),
            delta=float(r["delta"]) if r.get("delta") not in (None, "") else None,
            volume=float(r.get("volume") or 0),
            open_interest=float(r.get("oi") or r.get("open_interest") or 0),
        ))
    return out


async def _kite_bars(user_id: str, interval: str = "5m", limit: int = 240) -> list[Bar]:
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
    candidates = []
    for r in instruments:
        if str(r.get("name") or "").upper() != "NIFTY": continue
        typ = str(r.get("instrument_type") or "").upper()
        if typ not in {"CE", "PE"}: continue
        expiry = str(r.get("expiry") or "")[:10]
        if not expiry: continue
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        except ValueError:
            continue
        if exp_date < today: continue
        if (typ == "CE" and direction == "LONG") or (typ == "PE" and direction == "SHORT"):
            candidates.append((exp_date, r))
    if not candidates:
        raise RuntimeError("No NIFTY option contracts available")
    nearest = min(x[0] for x in candidates)
    contracts: list[OptionContract] = []
    for exp_date, r in candidates:
        if exp_date != nearest: continue
        symbol = str(r.get("tradingsymbol") or "")
        try:
            q = await client.get_quote([f"NFO:{symbol}"])
            data = q.get(f"NFO:{symbol}", {}) or {}
            ltp = float(data.get("last_price") or 0)
            depth = data.get("depth") or {}
            buy = (depth.get("buy") or [{}])[0]
            sell = (depth.get("sell") or [{}])[0]
            contracts.append(OptionContract(
                symbol=symbol,
                strike=float(r.get("strike") or 0),
                expiry=exp_date.isoformat(),
                option_type=str(r.get("instrument_type")),
                ltp=ltp,
                bid=float(buy.get("price") or 0),
                ask=float(sell.get("price") or 0),
                lot_size=int(r.get("lot_size") or 1),
                volume=float(data.get("volume") or 0),
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
        spot, contracts = await _kite_spot_and_options(user_id, "LONG")
        if not contracts:
            _, contracts = await _kite_spot_and_options(user_id, "SHORT")
    else:
        from app.services.market_data.truedata import TrueDataHistoricalClient
        client = TrueDataHistoricalClient(settings.truedata_username, settings.truedata_password, timeout=settings.truedata_timeout_seconds)
        try:
            bars_raw = await client.get_last_bars(cfg.truedata_underlying_symbol if hasattr(cfg, "truedata_underlying_symbol") else "NIFTY 50", 200, interval=f"{cfg.interval_minutes}min")
            bars = [_bar_from_any(r) for r in bars_raw]
            spot = bars[-1].close
            contracts = []
            # TrueData option-chain is only fetched after a directional signal to avoid unnecessary API calls.
            contracts_payload = None
        finally:
            await client.aclose()
    signal = generate_signal(bars, cfg)
    plan = None
    if signal.direction != "NONE":
        if cfg.data_source == "truedata":
            client = TrueDataHistoricalClient(settings.truedata_username, settings.truedata_password, timeout=settings.truedata_timeout_seconds)
            try:
                chain = await client.get_option_chain("NIFTY", "nearest")
                contracts = normalize_truedata_option_chain(chain)
            finally:
                await client.aclose()
        option = select_option(spot, signal.direction, contracts, cfg)
        plan = build_trade_plan(signal, option, cfg, spot=spot)
    return {"enabled": True, "data_source": cfg.data_source, "execution_broker": cfg.execution_broker, "signal": signal.to_dict(), "plan": plan.to_dict() if plan else None}


def backtest_from_bars(rows: list[dict[str, Any]], cfg: StrategyConfig | None = None) -> dict[str, Any]:
    """Underlying-level walk-forward replay used as the deterministic baseline.

    It deliberately reports point/R statistics, not fabricated option P&L. Actual
    option replay must use historical option contracts/premiums from the selected
    source; this function is the signal validation layer.
    """
    cfg = cfg or get_config()
    bars = [_bar_from_any(r) for r in rows]
    if len(bars) < 100:
        return {"metrics": summarize_pnl([]), "warning": "At least 100 bars are required"}
    pnls: list[float] = []
    current_day = None
    day_trades = 0
    for i in range(60, len(bars)):
        prefix = bars[:i + 1]
        day = prefix[-1].timestamp.date()
        if day != current_day:
            current_day, day_trades = day, 0
        if day_trades >= cfg.max_trades_per_day:
            continue
        signal = generate_signal(prefix, cfg)
        if signal.direction == "NONE":
            continue
        entry = prefix[-1].close
        stop = entry - signal.atr * cfg.stop_buffer_atr if signal.direction == "LONG" else entry + signal.atr * cfg.stop_buffer_atr
        target = entry + signal.atr * cfg.target_r if signal.direction == "LONG" else entry - signal.atr * cfg.target_r
        outcome = None
        for b in bars[i + 1:]:
            if b.timestamp.date() != day:
                break
            if signal.direction == "LONG":
                if b.low <= stop: outcome = -(entry - stop); break
                if b.high >= target: outcome = target - entry; break
            else:
                if b.high >= stop: outcome = -(stop - entry); break
                if b.low <= target: outcome = entry - target; break
        if outcome is not None:
            pnls.append(outcome)
            day_trades += 1
    metrics = summarize_pnl(pnls)
    metrics["model"] = "underlying-point baseline"
    metrics["costs_included"] = False
    return {"metrics": metrics, "warning": "Baseline only; option-level replay requires historical option premiums."}
