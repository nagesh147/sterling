"""Realtime multi-underlying scanner for the independent NIFTY ORB family.

The scanner is deliberately signal-only. It never places an order. Execution is
owned by the universal Trading Mode and the ORB runtime after a concrete plan is
selected.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.engines.nifty_orb_options import Bar, StrategyConfig, generate_signal
from app.services.nifty_orb_options import _bar, get_config


def configured_underlyings(cfg: StrategyConfig) -> list[str]:
    """Return the configured, de-duplicated underlying universe in stable order."""
    values: list[str] = []
    for raw in (*getattr(cfg, "scan_indices", ()) or (), *getattr(cfg, "scan_stocks", ()) or ()):
        symbol = str(raw).strip().upper()
        if symbol and symbol not in values:
            values.append(symbol)
    if not values and cfg.underlying:
        values.append(str(cfg.underlying).upper())
    if not getattr(cfg, "scan_stock_contracts", True):
        stock_names = {str(x).upper() for x in getattr(cfg, "scan_stocks", ()) or ()}
        # Registry names for indices are canonical and are not in stock_names.
        values = [x for x in values if x not in stock_names]
    return values


def _kite_symbol(underlying: str) -> str:
    from app.services.exchanges import instrument_registry as reg
    meta = reg.get_instrument(underlying)
    if meta is not None and getattr(meta, "zerodha_index_symbol", ""):
        return str(meta.zerodha_index_symbol)
    return f"NSE:{underlying}"


async def _kite_bars_for_underlying(uid: str, underlying: str, interval: str) -> list[Bar]:
    from app.services.exchanges.kite import accounts as accounts
    acct = accounts.get_active(uid)
    if not acct:
        raise RuntimeError("No active Kite account")
    client = await accounts.acquire_client(acct)
    rows = await client.get_candles(_kite_symbol(underlying), interval, limit=240)
    return [_bar({
        "timestamp_ms": r.timestamp_ms,
        "open": r.open,
        "high": r.high,
        "low": r.low,
        "close": r.close,
        "volume": r.volume,
    }) for r in rows]


async def _truedata_bars_for_underlying(underlying: str, interval: str) -> list[Bar]:
    from app.services.market_data.truedata import TrueDataHistoricalClient
    from app.core.config import settings
    client = TrueDataHistoricalClient(
        settings.truedata_username,
        settings.truedata_password,
        timeout=settings.truedata_timeout_seconds,
    )
    try:
        # TrueData symbol aliases are intentionally kept at this boundary. The
        # signal engine never knows which vendor produced the bars.
        aliases = {"NIFTY": "NIFTY 50", "BANKNIFTY": "NIFTY BANK"}
        symbol = aliases.get(underlying, underlying)
        rows = await client.get_last_bars(symbol, 240, interval=f"{interval}min")
        return [_bar(row) for row in rows]
    finally:
        await client.aclose()


async def scan_underlying(uid: str, underlying: str, cfg: StrategyConfig | None = None) -> dict[str, Any]:
    cfg = cfg or get_config()
    symbol = str(underlying).upper()
    local_cfg = StrategyConfig(**{**cfg.__dict__, "underlying": symbol})
    if cfg.data_source == "kite":
        bars = await _kite_bars_for_underlying(uid, symbol, f"{cfg.interval_minutes}m")
    elif cfg.data_source == "truedata":
        bars = await _truedata_bars_for_underlying(symbol, str(cfg.interval_minutes))
    else:
        raise ValueError(f"Unsupported ORB data source: {cfg.data_source}")
    if not bars:
        return {"underlying": symbol, "status": "no_data", "signal": None}
    signal = generate_signal(bars, local_cfg)
    return {
        "underlying": symbol,
        "status": "signal" if signal.direction != "NONE" else "watching",
        "signal": signal.to_dict(),
        "spot": bars[-1].close,
        "interval_minutes": cfg.interval_minutes,
        "data_source": cfg.data_source,
    }


async def scan_user(uid: str, cfg: StrategyConfig | None = None) -> dict[str, Any]:
    """Scan every configured underlying concurrently with per-symbol isolation."""
    cfg = cfg or get_config()
    if not cfg.enabled:
        return {"enabled": False, "signals": [], "universe": []}
    universe = configured_underlyings(cfg)
    results = await asyncio.gather(
        *(scan_underlying(uid, symbol, cfg) for symbol in universe),
        return_exceptions=True,
    )
    rows: list[dict[str, Any]] = []
    for symbol, result in zip(universe, results):
        if isinstance(result, Exception):
            rows.append({"underlying": symbol, "status": "error", "signal": None, "error": str(result)})
        else:
            rows.append(result)
    rows.sort(key=lambda row: (row.get("status") != "signal", row["underlying"]))
    return {
        "enabled": True,
        "universe": universe,
        "signals": rows,
        "signal_count": sum(1 for row in rows if row.get("status") == "signal"),
        "data_source": cfg.data_source,
    }
