"""Realtime multi-underlying scanner for the independent NIFTY ORB family.

The scanner is signal-only. It never places an order. It resolves the option BUY
vehicle alongside every live signal so the Signals surface can show an actionable
CE/PE trade without coupling the strategy to Adaptive Edge, SuperTrend or Navigator.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from app.engines.nifty_orb_options import Bar, OptionContract, StrategyConfig, build_trade_plan, generate_signal, select_option
from app.services.nifty_orb_options import _bar, get_config, normalize_option_chain

_IST = timezone(timedelta(hours=5, minutes=30))
_BAR_CACHE_TTL_S = 4.0
_bar_cache: dict[tuple[str, str, str], tuple[float, list[Bar]]] = {}
_option_cache: dict[tuple[str, str, str], tuple[float, list[OptionContract]]] = {}


def _canonical(symbol: str) -> str:
    return {
        "NIFTY 50": "NIFTY",
        "NIFTY BANK": "BANKNIFTY",
        "NIFTY FIN SERVICE": "FINNIFTY",
    }.get(symbol.strip().upper(), symbol.strip().upper())


def configured_underlyings(cfg: StrategyConfig) -> list[str]:
    """Resolve the configured index + eligible stock universe deterministically."""
    values: list[str] = []
    for raw in getattr(cfg, "scan_indices", ()) or ():
        symbol = _canonical(str(raw))
        if symbol and symbol not in values:
            values.append(symbol)
    if getattr(cfg, "scan_stock_contracts", True):
        selected = [_canonical(str(x)) for x in (getattr(cfg, "scan_stocks", ()) or ())]
        if getattr(cfg, "scan_all_stocks", False):
            try:
                from app.services.kite_engine.stock_registry import CURATED_STOCK_NAMES
                selected = list(CURATED_STOCK_NAMES)
            except Exception:
                pass
        for symbol in selected:
            if symbol and symbol not in values:
                values.append(symbol)
    if not values and cfg.underlying:
        values.append(_canonical(str(cfg.underlying)))
    return values


def _kite_symbol(underlying: str) -> str:
    from app.services.exchanges import instrument_registry as reg
    meta = reg.get_instrument(underlying)
    if meta is not None and getattr(meta, "zerodha_index_symbol", ""):
        return str(meta.zerodha_index_symbol)
    return f"NSE:{underlying}"


async def _kite_bars_for_underlying(uid: str, underlying: str, interval: str) -> list[Bar]:
    from app.services.exchanges.kite import accounts
    acct = accounts.get_active(uid)
    if not acct:
        raise RuntimeError("No active Kite account")
    key = (uid, underlying, interval)
    cached = _bar_cache.get(key)
    if cached and (datetime.now().timestamp() - cached[0]) < _BAR_CACHE_TTL_S:
        return cached[1]
    client = await accounts.acquire_client(acct)
    rows = await client.get_candles(_kite_symbol(underlying), interval, limit=240)
    bars = [_bar({"timestamp_ms":r.timestamp_ms,"open":r.open,"high":r.high,"low":r.low,"close":r.close,"volume":r.volume}) for r in rows]
    _bar_cache[key] = (datetime.now().timestamp(), bars)
    return bars


async def _truedata_bars_for_underlying(underlying: str, interval: str) -> list[Bar]:
    from app.services.market_data.truedata import TrueDataHistoricalClient
    from app.core.config import settings
    client = TrueDataHistoricalClient(settings.truedata_username,settings.truedata_password,timeout=settings.truedata_timeout_seconds)
    try:
        aliases={"NIFTY":"NIFTY 50","BANKNIFTY":"NIFTY BANK","FINNIFTY":"NIFTY FIN SERVICE"}
        rows=await client.get_last_bars(aliases.get(underlying,underlying),240,interval=f"{interval}min")
        return [_bar(row) for row in rows]
    finally:
        await client.aclose()


async def _kite_option_contracts(uid: str, underlying: str, direction: str) -> list[OptionContract]:
    from app.services.exchanges.kite import accounts
    acct=accounts.get_active(uid)
    if not acct: raise RuntimeError("No active Kite account")
    wanted="CE" if direction=="LONG" else "PE"
    key=(uid,underlying,wanted);cached=_option_cache.get(key)
    if cached and (datetime.now().timestamp()-cached[0])<_BAR_CACHE_TTL_S:return cached[1]
    client=await accounts.acquire_client(acct)
    lookup_name={"NIFTY":"NIFTY","BANKNIFTY":"BANKNIFTY","FINNIFTY":"FINNIFTY"}.get(underlying,underlying)
    rows=[]
    for exchange in ("NFO","BFO"):
        try:rows.extend(await client.search_instruments(lookup_name,exchange,limit=10000))
        except Exception:continue
    today=datetime.now(_IST).date();candidates=[]
    for row in rows:
        if str(row.get("name") or "").upper()!=lookup_name.upper() or str(row.get("instrument_type") or "").upper()!=wanted:continue
        try:expiry=datetime.strptime(str(row.get("expiry"))[:10],"%Y-%m-%d").date()
        except (TypeError,ValueError):continue
        if expiry>=today:candidates.append(row)
    if not candidates:return []
    expiries=sorted({str(r.get("expiry"))[:10] for r in candidates})[:2];selected=[r for r in candidates if str(r.get("expiry"))[:10] in expiries];contracts=[]
    for row in selected:
        symbol=str(row.get("tradingsymbol") or "")
        if not symbol:continue
        exchange=str(row.get("exchange") or "NFO").upper()
        try:
            quote=await client.get_quote([f"{exchange}:{symbol}"]);q=(quote or {}).get(f"{exchange}:{symbol}",{}) or {};depth=q.get("depth") or {};bid=(depth.get("buy") or [{}])[0];ask=(depth.get("sell") or [{}])[0]
            contracts.append(OptionContract(symbol,float(row.get("strike") or 0),str(row.get("expiry") or "")[:10],wanted,float(q.get("last_price") or 0),float(bid.get("price") or 0),float(ask.get("price") or 0),int(row.get("lot_size") or 1),float(q.get("delta")) if q.get("delta") not in (None,"") else None,float(q.get("volume") or 0),float(q.get("oi") or 0)))
        except Exception:continue
    _option_cache[key]=(datetime.now().timestamp(),contracts);return contracts


async def _option_contracts(uid:str,underlying:str,direction:str,cfg:StrategyConfig)->list[OptionContract]:
    if cfg.data_source=="kite":return await _kite_option_contracts(uid,underlying,direction)
    from app.services.market_data.truedata import TrueDataHistoricalClient
    from app.core.config import settings
    client=TrueDataHistoricalClient(settings.truedata_username,settings.truedata_password,timeout=settings.truedata_timeout_seconds)
    try:return normalize_option_chain(await client.get_option_chain(underlying,cfg.expiry_selection))
    finally:await client.aclose()


async def scan_underlying(uid:str,underlying:str,cfg:StrategyConfig|None=None)->dict[str,Any]:
    cfg=cfg or get_config();symbol=_canonical(str(underlying));local_cfg=StrategyConfig(**{**cfg.__dict__,"underlying":symbol});interval=f"{cfg.interval_minutes}m"
    bars=await _kite_bars_for_underlying(uid,symbol,interval) if cfg.data_source=="kite" else await _truedata_bars_for_underlying(symbol,str(cfg.interval_minutes))
    if not bars:return {"underlying":symbol,"status":"no_data","signal":None,"trade":None}
    signal=generate_signal(bars,local_cfg);result={"underlying":symbol,"status":"signal" if signal.direction!="NONE" else "watching","signal":signal.to_dict(),"spot":bars[-1].close,"interval_minutes":cfg.interval_minutes,"data_source":cfg.data_source,"trade":None}
    if signal.direction=="NONE":return result
    try:
        contracts=await _option_contracts(uid,symbol,signal.direction,cfg);option=select_option(bars[-1].close,signal.direction,contracts,cfg);result["trade"]=build_trade_plan(signal,option,cfg,spot=bars[-1].close).to_dict()
    except (ValueError,RuntimeError) as exc:result["status"]="signal_unresolved";result["trade_error"]=str(exc)
    return result


async def scan_user(uid:str,cfg:StrategyConfig|None=None)->dict[str,Any]:
    cfg=cfg or get_config()
    if not cfg.enabled:return {"enabled":False,"signals":[],"universe":[]}
    universe=configured_underlyings(cfg);results=await asyncio.gather(*(scan_underlying(uid,s,cfg) for s in universe),return_exceptions=True);rows=[]
    for symbol,result in zip(universe,results):rows.append({"underlying":symbol,"status":"error","signal":None,"trade":None,"error":str(result)} if isinstance(result,Exception) else result)
    rows.sort(key=lambda row:(row.get("status") not in {"signal","signal_unresolved"},row["underlying"]))
    return {"enabled":True,"universe":universe,"signals":rows,"signal_count":sum(1 for row in rows if row.get("status") in {"signal","signal_unresolved"}),"data_source":cfg.data_source}
