"""Realtime multi-underlying scanner for the independent NIFTY ORB family."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from app.engines.nifty_orb_options import Bar, OptionContract, StrategyConfig, build_trade_plan, generate_signal, select_option
from app.services.nifty_orb_options import _bar, get_config
from app.services.providers.truedata.orb_provider import TrueDataOrbProvider

_IST = timezone(timedelta(hours=5, minutes=30))
_BAR_CACHE_TTL_S = 4.0
_option_cache: dict[tuple, tuple[float, list[OptionContract]]] = {}
_bar_cache: dict[tuple[str, str, str], tuple[float, list[Bar]]] = {}


def _canonical(symbol: str) -> str:
    return {"NIFTY 50": "NIFTY", "NIFTY BANK": "BANKNIFTY", "FINNIFTY": "FINNIFTY", "NIFTY FIN SERVICE": "FINNIFTY"}.get(symbol.strip().upper(), symbol.strip().upper())


def _truedata_symbol(underlying: str) -> str:
    return {"NIFTY": "NIFTY 50", "BANKNIFTY": "NIFTY BANK", "FINNIFTY": "NIFTY FIN SERVICE"}.get(underlying, underlying)


def configured_underlyings(cfg: StrategyConfig) -> list[str]:
    values: list[str] = []
    for raw in cfg.scan_indices or ():
        s = _canonical(str(raw))
        if s and s not in values:
            values.append(s)
    if cfg.scan_stock_contracts:
        selected = [_canonical(str(x)) for x in (cfg.scan_stocks or ())]
        if cfg.scan_all_stocks:
            try:
                from app.services.kite_engine.stock_registry import CURATED_STOCK_NAMES
                selected = list(CURATED_STOCK_NAMES)
            except Exception:
                pass
        for s in selected:
            if s and s not in values:
                values.append(s)
    if not values and cfg.underlying:
        values.append(_canonical(cfg.underlying))
    return values


def _kite_symbol(underlying: str) -> str:
    from app.services.exchanges import instrument_registry as reg
    meta = reg.get_instrument(underlying)
    return str(meta.zerodha_index_symbol) if meta is not None and getattr(meta, "zerodha_index_symbol", "") else f"NSE:{underlying}"


def _completed_bars(bars: list[Bar], interval_minutes: int, now: datetime | None = None) -> list[Bar]:
    """Drop the currently-forming candle; keep a candle exactly at its close time."""
    now_ist = (now or datetime.now(_IST)).astimezone(_IST)
    interval = max(1, int(interval_minutes))
    out: list[Bar] = []
    for bar in bars:
        ts = bar.timestamp.astimezone(_IST) if bar.timestamp.tzinfo else bar.timestamp.replace(tzinfo=_IST)
        ts = ts.replace(second=0, microsecond=0)
        close_time = ts + timedelta(minutes=interval)
        if close_time <= now_ist:
            out.append(bar)
    return out


async def _kite_bars_for_underlying(uid: str, underlying: str, interval: str) -> list[Bar]:
    from app.services.exchanges.kite import accounts
    acct = accounts.get_active(uid)
    if not acct:
        raise RuntimeError("No active Kite account")
    key = (uid, underlying, interval)
    cached = _bar_cache.get(key)
    if cached and datetime.now().timestamp() - cached[0] < _BAR_CACHE_TTL_S:
        return _completed_bars(cached[1], int(interval.rstrip("m")))
    client = await accounts.acquire_client(acct)
    rows = await client.get_candles(_kite_symbol(underlying), interval, limit=240)
    bars = [_bar({"timestamp_ms": r.timestamp_ms, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume}) for r in rows]
    _bar_cache[key] = (datetime.now().timestamp(), bars)
    return _completed_bars(bars, int(interval.rstrip("m")))


async def _truedata_bars_for_underlying(underlying: str, interval: str) -> list[Bar]:
    from app.core.config import settings
    from app.services.market_data.truedata import TrueDataHistoricalClient
    client = TrueDataHistoricalClient(settings.truedata_username, settings.truedata_password, timeout=settings.truedata_timeout_seconds)
    try:
        bars = await TrueDataOrbProvider(client).bars(_truedata_symbol(underlying), StrategyConfig(interval_minutes=int(interval)))
        return _completed_bars(bars, int(interval))
    finally:
        await client.aclose()


def _selection_config(cfg: StrategyConfig) -> StrategyConfig:
    """Disable validation that cannot be supported by the selected TrueData feeds."""
    if cfg.data_source != "truedata":
        return cfg
    return replace(
        cfg,
        min_open_interest=cfg.min_open_interest if cfg.truedata_use_oi else 0.0,
        max_spread_pct=cfg.max_spread_pct,
    )


def _expiry_for_mode(eligible: list[tuple], mode: str):
    if not eligible:
        return None
    mode = mode.lower()
    if mode == "nearest" or mode == "weekly":
        # Weekly is the earliest eligible expiry. The nearest expiry is also the
        # weekly contract whenever a weekly series is listed for the underlying.
        return min(exp for exp, _ in eligible)
    if mode == "monthly":
        month = min((exp.year, exp.month) for exp, _ in eligible)
        same_month = [exp for exp, _ in eligible if (exp.year, exp.month) == month]
        return max(same_month)
    raise ValueError("expiry_selection must be nearest, weekly or monthly")


async def _kite_option_contracts(uid: str, underlying: str, direction: str, cfg: StrategyConfig) -> list[OptionContract]:
    from app.services.exchanges.kite import accounts
    acct = accounts.get_active(uid)
    if not acct:
        raise RuntimeError("No active Kite account")
    wanted = "CE" if direction == "LONG" else "PE"
    cache_key = (uid, underlying, wanted, cfg.expiry_selection, cfg.expiry_dte_min, cfg.expiry_dte_max, cfg.avoid_expiry_day, datetime.now(_IST).date().isoformat())
    cached = _option_cache.get(cache_key)
    if cached and datetime.now().timestamp() - cached[0] < _BAR_CACHE_TTL_S:
        return cached[1]

    client = await accounts.acquire_client(acct)
    rows = []
    for exchange in ("NFO", "BFO"):
        try:
            rows.extend(await client.search_instruments(underlying, exchange, limit=10000))
        except Exception:
            continue
    today = datetime.now(_IST).date()
    eligible = []
    for row in rows:
        if str(row.get("name") or "").upper() != underlying.upper() or str(row.get("instrument_type") or "").upper() != wanted:
            continue
        try:
            exp = datetime.strptime(str(row.get("expiry"))[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        dte = (exp - today).days
        if dte < cfg.expiry_dte_min or dte > cfg.expiry_dte_max or (cfg.avoid_expiry_day and dte == 0):
            continue
        eligible.append((exp, row))
    selected_expiry = _expiry_for_mode(eligible, cfg.expiry_selection)
    if selected_expiry is None:
        return []

    contracts: list[OptionContract] = []
    for exp, row in eligible:
        if exp != selected_expiry:
            continue
        symbol = str(row.get("tradingsymbol") or "")
        exchange = str(row.get("exchange") or "NFO").upper()
        if not symbol:
            continue
        try:
            key = f"{exchange}:{symbol}"
            q = (await client.get_quote([key]) or {}).get(key, {}) or {}
            depth = q.get("depth") or {}
            bid = (depth.get("buy") or [{}])[0]
            ask = (depth.get("sell") or [{}])[0]
            contracts.append(OptionContract(
                symbol=symbol,
                strike=float(row.get("strike") or 0),
                expiry=exp.isoformat(),
                option_type=wanted,
                ltp=float(q.get("last_price") or 0),
                bid=float(bid.get("price") or 0),
                ask=float(ask.get("price") or 0),
                lot_size=int(row.get("lot_size") or 1),
                delta=float(q["delta"]) if q.get("delta") not in (None, "") else None,
                volume=float(q.get("volume") or 0),
                open_interest=float(q.get("oi") or 0),
            ))
        except Exception:
            continue
    _option_cache[cache_key] = (datetime.now().timestamp(), contracts)
    return contracts


async def _truedata_option_contracts(underlying: str, direction: str, cfg: StrategyConfig) -> list[OptionContract]:
    from app.core.config import settings
    from app.services.market_data.truedata import TrueDataHistoricalClient
    client = TrueDataHistoricalClient(settings.truedata_username, settings.truedata_password, timeout=settings.truedata_timeout_seconds)
    try:
        return await TrueDataOrbProvider(client).option_chain(underlying, cfg.expiry_selection, cfg)
    finally:
        await client.aclose()


async def _truedata_refresh_option(contract: OptionContract, cfg: StrategyConfig) -> tuple[OptionContract, float | None]:
    needs_tick = cfg.truedata_use_ticks or cfg.truedata_use_quote_freshness or cfg.truedata_use_bid_ask
    if not needs_tick and not cfg.truedata_use_oi:
        return contract, None
    from app.core.config import settings
    from app.services.market_data.truedata import TrueDataHistoricalClient
    client = TrueDataHistoricalClient(settings.truedata_username, settings.truedata_password, timeout=settings.truedata_timeout_seconds)
    try:
        tick = await TrueDataOrbProvider(client).latest_tick(contract.symbol, bidask=cfg.truedata_use_bid_ask)
    finally:
        await client.aclose()
    if not tick:
        if cfg.truedata_use_quote_freshness or cfg.truedata_use_bid_ask:
            raise ValueError("TrueData quote is unavailable")
        return contract, None

    raw = tick.get("timestamp") or tick.get("time")
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if "T" in str(raw) else datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_IST)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=_IST)
        age = max(0.0, datetime.now(_IST).timestamp() - ts.timestamp())
        quote_ts = ts.astimezone(_IST)
    except Exception:
        age = None
        quote_ts = None

    ltp = float(tick.get("ltp") or contract.ltp)
    bid = float(tick.get("bid") or contract.bid)
    ask = float(tick.get("ask") or contract.ask)
    volume = float(tick.get("volume") or contract.volume)
    oi = float(tick.get("oi") or contract.open_interest)
    if cfg.truedata_use_bid_ask and (bid <= 0 or ask < bid):
        raise ValueError("invalid TrueData bid/ask")
    if cfg.truedata_use_quote_freshness and (age is None or age > cfg.max_quote_staleness_s):
        raise ValueError(f"stale TrueData quote: {age if age is not None else 'unknown'}s")
    if cfg.truedata_use_oi and oi < cfg.min_open_interest:
        raise ValueError("TrueData OI below configured minimum")

    refreshed = OptionContract(contract.symbol, contract.strike, contract.expiry, contract.option_type, ltp, bid, ask, contract.lot_size, contract.delta, volume, oi, quote_ts)
    if cfg.truedata_use_bid_ask and refreshed.spread_pct > cfg.max_spread_pct:
        raise ValueError("TrueData spread above configured maximum")
    if volume < cfg.min_option_volume:
        raise ValueError("TrueData option volume below configured minimum")
    return refreshed, age


async def _option_contracts(uid: str, underlying: str, direction: str, cfg: StrategyConfig) -> list[OptionContract]:
    if cfg.data_source == "kite":
        return await _kite_option_contracts(uid, underlying, direction, cfg)
    return await _truedata_option_contracts(underlying, direction, cfg)


async def scan_underlying(uid: str, underlying: str, cfg: StrategyConfig | None = None) -> dict[str, Any]:
    cfg = cfg or get_config()
    symbol = _canonical(underlying)
    local = StrategyConfig(**{**cfg.__dict__, "underlying": symbol})
    interval = str(cfg.interval_minutes)
    bars = await (_kite_bars_for_underlying(uid, symbol, f"{interval}m") if cfg.data_source == "kite" else _truedata_bars_for_underlying(symbol, interval))
    if not bars:
        return {"underlying": symbol, "status": "no_data", "signal": None, "trade": None}

    now = datetime.now(_IST)
    signal = generate_signal(bars, local, as_of=now)
    result = {
        "underlying": symbol,
        "status": "signal" if signal.direction != "NONE" else "watching",
        "signal": signal.to_dict(),
        "spot": bars[-1].close,
        "interval_minutes": cfg.interval_minutes,
        "data_source": cfg.data_source,
        "trade": None,
    }
    if signal.direction == "NONE":
        return result
    try:
        contracts = await _option_contracts(uid, symbol, signal.direction, cfg)
        option = select_option(bars[-1].close, signal.direction, contracts, _selection_config(cfg))
        quote_age = None
        if cfg.data_source == "truedata":
            option, quote_age = await _truedata_refresh_option(option, cfg)
        result["trade"] = build_trade_plan(signal, option, cfg, spot=bars[-1].close).to_dict()
        if quote_age is not None:
            result["quote_age_s"] = round(quote_age, 2)
    except (ValueError, RuntimeError) as exc:
        result["status"] = "signal_unresolved"
        result["trade_error"] = str(exc)
    return result


async def scan_user(uid: str, cfg: StrategyConfig | None = None) -> dict[str, Any]:
    cfg = cfg or get_config()
    if not cfg.enabled:
        return {"enabled": False, "signals": [], "universe": []}
    universe = configured_underlyings(cfg)
    results = await asyncio.gather(*(scan_underlying(uid, s, cfg) for s in universe), return_exceptions=True)
    rows = []
    for symbol, result in zip(universe, results):
        rows.append({"underlying": symbol, "status": "error", "signal": None, "trade": None, "error": str(result)} if isinstance(result, Exception) else result)
    rows.sort(key=lambda r: (r.get("status") not in {"signal", "signal_unresolved"}, r["underlying"]))
    return {
        "enabled": True,
        "universe": universe,
        "signals": rows,
        "signal_count": sum(1 for r in rows if r.get("status") in {"signal", "signal_unresolved"}),
        "data_source": cfg.data_source,
    }
