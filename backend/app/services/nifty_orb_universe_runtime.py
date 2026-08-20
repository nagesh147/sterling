"""Kite runtime adapter for the broker-agnostic NIFTY ORB universe scanner."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.engines.nifty_orb_options import Bar, StrategyConfig
from app.engines.nifty_orb_universe import UniverseInstrument, UniverseScanConfig, UniverseSignal, scan_universe
from app.schemas.instruments import InstrumentMeta
from app.services.exchanges import instrument_registry as registry

_IST = timezone(timedelta(hours=5, minutes=30))
_INDEX_ALIASES = {"NIFTY": "NIFTY", "NIFTY 50": "NIFTY", "BANKNIFTY": "BANKNIFTY", "NIFTY BANK": "BANKNIFTY"}


def _value(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def _bar(row: Any) -> Bar:
    ts = _value(row, "timestamp_ms")
    if ts is not None:
        dt = datetime.fromtimestamp(float(ts) / 1000.0, tz=_IST)
    else:
        raw = _value(row, "timestamp")
        if isinstance(raw, datetime):
            dt = raw if raw.tzinfo else raw.replace(tzinfo=_IST)
        else:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_IST)
    return Bar(
        dt,
        float(_value(row, "open", 0)),
        float(_value(row, "high", 0)),
        float(_value(row, "low", 0)),
        float(_value(row, "close", 0)),
        float(_value(row, "volume", 0) or 0),
    )


def _stock_meta(symbol: str, row: dict, *, exchange: str = "NSE") -> InstrumentMeta:
    """Build InstrumentMeta from a Kite instrument row.

    ``exchange`` prefixes the quote key, so a BSE index does not get an NSE
    prefix that would make every quote lookup miss.
    """
    return InstrumentMeta(
        underlying=symbol,
        quote_currency="INR",
        contract_multiplier=1.0,
        tick_size=float(row.get("tick_size") or 0.05),
        strike_step=1.0,
        has_options=True,
        exchange="zerodha",
        exchange_currency="INR",
        perp_symbol="",
        index_name=str(row.get("tradingsymbol") or symbol),
        zerodha_token=int(row.get("instrument_token") or 0),
        zerodha_index_symbol=f"{exchange}:{row.get('tradingsymbol') or symbol}",
        description="NSE F&O equity underlying",
    )


async def discover_universe(client, cfg: StrategyConfig, *, max_candidates: int) -> list[UniverseInstrument]:
    """Resolve configured indices/stocks and optionally discover F&O stocks.

    Discovery is performed from the cached NFO instrument dump. It does not issue
    one network request per stock. Explicit symbols are retained first, followed
    by discovered symbols in deterministic alphabetical order.
    """
    items: list[UniverseInstrument] = []
    seen: set[str] = set()

    requested_indices = cfg.scan_indices if cfg.scan_indices else (cfg.underlying,)
    for raw in requested_indices:
        canonical = _INDEX_ALIASES.get(str(raw).strip().upper(), str(raw).strip().upper())
        if canonical in {"NIFTY", "BANKNIFTY"} and canonical not in seen:
            if registry.get_instrument(canonical):
                items.append(UniverseInstrument(canonical, "index"))
                seen.add(canonical)

    explicit = [str(x).strip().upper() for x in cfg.scan_stocks]
    for symbol in explicit:
        if symbol and symbol not in seen:
            items.append(UniverseInstrument(symbol, "stock"))
            seen.add(symbol)

    if cfg.scan_all_stocks:
        rows = await client.search_instruments("", "NFO", limit=100000)
        discovered = sorted({
            str(row.get("name") or "").upper()
            for row in rows
            if str(row.get("instrument_type") or "").upper() in {"CE", "PE"}
            and str(row.get("name") or "").strip()
            and str(row.get("name") or "").upper() not in {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}
        })
        for symbol in discovered:
            if symbol not in seen:
                items.append(UniverseInstrument(symbol, "stock"))
                seen.add(symbol)
            if len(items) >= max_candidates:
                break

    return items[:max_candidates]


async def scan_kite_universe(uid: str, cfg: StrategyConfig, *, max_candidates: int = 30, concurrency: int = 6) -> list[UniverseSignal]:
    from app.services.exchanges.kite import accounts as accounts

    account = accounts.get_active(uid)
    if not account:
        raise RuntimeError("No active Kite account")
    client = await accounts.acquire_client(account)
    instruments = await discover_universe(client, cfg, max_candidates=max_candidates)
    meta_cache: dict[str, InstrumentMeta] = {}

    async def fetch_bars(item: UniverseInstrument, strategy_cfg: StrategyConfig):
        meta = meta_cache.get(item.symbol)
        if meta is None:
            if item.kind == "index":
                meta = registry.get_instrument(item.symbol)
                if meta is None:
                    raise RuntimeError(f"Unsupported index: {item.symbol}")
            else:
                rows = await client.search_instruments(item.symbol, "NSE", limit=20)
                exact = next((r for r in rows if str(r.get("tradingsymbol") or "").upper() == item.symbol), None)
                if exact is None or str(exact.get("instrument_type") or "").upper() != "EQ":
                    raise RuntimeError(f"NSE equity instrument unavailable: {item.symbol}")
                meta = _stock_meta(item.symbol, exact)
            meta_cache[item.symbol] = meta
        rows = await client.get_candles(meta, f"{strategy_cfg.interval_minutes}m", limit=240)
        return [_bar(row) for row in rows]

    return await scan_universe(
        instruments,
        strategy_config=cfg,
        scan_config=UniverseScanConfig(max_candidates=max_candidates, concurrency=concurrency),
        fetch_bars=fetch_bars,
    )
