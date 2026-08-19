"""Realtime multi-underlying scanner for the independent NIFTY ORB family."""
from __future__ import annotations
import asyncio
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from typing import Any
from app.engines.nifty_orb_options import Bar,OptionContract,StrategyConfig,build_trade_plan,generate_signal,select_option
from app.services.nifty_orb_options import _bar,get_config,normalize_option_chain
from app.services.nifty_orb_option_chain import filter_chain
_IST=timezone(timedelta(hours=5,minutes=30));_BAR_CACHE_TTL_S=4.0;_option_cache:dict[tuple[str,str,str],tuple[float,list[OptionContract]]]={};_bar_cache:dict[tuple[str,str,str],tuple[float,list[Bar]]]={}
def _canonical(symbol:str)->str:return {"NIFTY 50":"NIFTY","NIFTY BANK":"BANKNIFTY","NIFTY FIN SERVICE":"FINNIFTY"}.get(symbol.strip().upper(),symbol.strip().upper())
def configured_underlyings(cfg:StrategyConfig)->list[str]:
    values=[]
    for raw in cfg.scan_indices or ():
        s=_canonical(str(raw))
        if s and s not in values:values.append(s)
    if cfg.scan_stock_contracts:
        selected=[_canonical(str(x)) for x in (cfg.scan_stocks or ())]
        if cfg.scan_all_stocks:
            try:
                from app.services.kite_engine.stock_registry import CURATED_STOCK_NAMES;selected=list(CURATED_STOCK_NAMES)
            except Exception:pass
        for s in selected:
            if s and s not in values:values.append(s)
    if not values and cfg.underlying:values.append(_canonical(cfg.underlying))
    return values
def _kite_symbol(underlying:str)->str:
    from app.services.exchanges import instrument_registry as reg
    meta=reg.get_instrument(underlying)
    return str(meta.zerodha_index_symbol) if meta is not None and getattr(meta,"zerodha_index_symbol","") else f"NSE:{underlying}"
async def _kite_bars_for_underlying(uid:str,underlying:str,interval:str)->list[Bar]:
    from app.services.exchanges.kite import accounts
    acct=accounts.get_active(uid)
    if not acct:raise RuntimeError("No active Kite account")
    key=(uid,underlying,interval);cached=_bar_cache.get(key)
    if cached and datetime.now().timestamp()-cached[0]<_BAR_CACHE_TTL_S:return cached[1]
    client=await accounts.acquire_client(acct);rows=await client.get_candles(_kite_symbol(underlying),interval,limit=240);bars=[_bar({"timestamp_ms":r.timestamp_ms,"open":r.open,"high":r.high,"low":r.low,"close":r.close,"volume":r.volume}) for r in rows];_bar_cache[key]=(datetime.now().timestamp(),bars);return bars
async def _truedata_bars_for_underlying(underlying:str,interval:str)->list[Bar]:
    from app.services.market_data.truedata import TrueDataHistoricalClient
    from app.core.config import settings
    client=TrueDataHistoricalClient(settings.truedata_username,settings.truedata_password,timeout=settings.truedata_timeout_seconds)
    try:
        aliases={"NIFTY":"NIFTY 50","BANKNIFTY":"NIFTY BANK","FINNIFTY":"NIFTY FIN SERVICE"};rows=await client.get_last_bars(aliases.get(underlying,underlying),240,interval=f"{interval}min");return [_bar(r) for r in rows]
    finally:await client.aclose()
async def _kite_option_contracts(uid:str,underlying:str,direction:str,cfg:StrategyConfig)->list[OptionContract]:
    from app.services.exchanges.kite import accounts
    acct=accounts.get_active(uid)
    if not acct:raise RuntimeError("No active Kite account")
    wanted="CE" if direction=="LONG" else "PE";key=(uid,underlying,wanted);cached=_option_cache.get(key)
    if cached and datetime.now().timestamp()-cached[0]<_BAR_CACHE_TTL_S:return cached[1]
    client=await accounts.acquire_client(acct);lookup={"NIFTY":"NIFTY","BANKNIFTY":"BANKNIFTY","FINNIFTY":"FINNIFTY"}.get(underlying,underlying);rows=[]
    for exchange in ("NFO","BFO"):
        try:rows.extend(await client.search_instruments(lookup,exchange,limit=10000))
        except Exception:continue
    today=datetime.now(_IST).date();candidates=[]
    for row in rows:
        if str(row.get("name") or "").upper()!=lookup.upper() or str(row.get("instrument_type") or "").upper()!=wanted:continue
        try:exp=datetime.strptime(str(row.get("expiry"))[:10],"%Y-%m-%d").date()
        except (TypeError,ValueError):continue
        if exp>=today:candidates.append(row)
    expiries=sorted({str(r.get("expiry"))[:10] for r in candidates})[:2];selected=[r for r in candidates if str(r.get("expiry"))[:10] in expiries];contracts=[]
    for row in selected:
        symbol=str(row.get("tradingsymbol") or "");exchange=str(row.get("exchange") or "NFO").upper()
        if not symbol:continue
        try:
            q=(await client.get_quote([f"{exchange}:{symbol}"]) or {}).get(f"{exchange}:{symbol}",{}) or {};depth=q.get("depth") or {};bid=(depth.get("buy") or [{}])[0];ask=(depth.get("sell") or [{}])[0]
            contracts.append(OptionContract(symbol,float(row.get("strike") or 0),str(row.get("expiry") or "")[:10],wanted,float(q.get("last_price") or 0),float(bid.get("price") or 0),float(ask.get("price") or 0),int(row.get("lot_size") or 1),float(q.get("delta")) if q.get("delta") not in (None,"") else None,float(q.get("volume") or 0),float(q.get("oi") or 0)))
        except Exception:continue
    _option_cache[key]=(datetime.now().timestamp(),contracts);return contracts
async def _truedata_option_contracts(underlying:str,direction:str,cfg:StrategyConfig)->list[OptionContract]:
    from app.services.market_data.truedata import TrueDataHistoricalClient
    from app.core.config import settings
    client=TrueDataHistoricalClient(settings.truedata_username,settings.truedata_password,timeout=settings.truedata_timeout_seconds)
    try:
        payload=await client.get_option_chain(underlying,cfg.expiry_selection);contracts=normalize_option_chain(payload)
        contracts=filter_chain(contracts,cfg)
        if not cfg.truedata_use_ticks or not cfg.truedata_use_quote_freshness:return contracts
        # Chain hydration is cheap; tick hydration is reserved for the already liquid set.
        # Refresh only the nearest candidates so advanced tick data does not multiply API load by the full chain size.
        wanted="CE" if direction=="LONG" else "PE";side=[c for c in contracts if c.option_type==wanted];side=sorted(side,key=lambda c:(c.dte or 999,c.spread_pct,-c.volume,-c.open_interest))[:6];refreshed=[]
        for c in side:
            try:
                ticks=await client.get_ticks(c.symbol,(datetime.now(_IST)-timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S"),datetime.now(_IST).strftime("%Y-%m-%d %H:%M:%S"),bidask=1)
                if ticks:
                    t=ticks[-1];ts=str(t.get("timestamp") or t.get("time") or "");qt=None
                    try:qt=datetime.fromisoformat(ts.replace("Z","+00:00")) if "T" in ts else datetime.strptime(ts,"%Y-%m-%d %H:%M:%S").replace(tzinfo=_IST)
                    except (TypeError,ValueError):pass
                    refreshed.append(replace(c,ltp=float(t.get("ltp") or c.ltp),bid=float(t.get("bid") or c.bid),ask=float(t.get("ask") or c.ask),volume=float(t.get("volume") or c.volume),open_interest=float(t.get("oi") or c.open_interest),quote_timestamp=qt))
            except Exception:continue
        return filter_chain(refreshed,cfg)
    finally:await client.aclose()
async def _option_contracts(uid:str,underlying:str,direction:str,cfg:StrategyConfig)->list[OptionContract]:
    return await _kite_option_contracts(uid,underlying,direction,cfg) if cfg.data_source=="kite" else await _truedata_option_contracts(underlying,direction,cfg)
async def scan_underlying(uid:str,underlying:str,cfg:StrategyConfig|None=None)->dict[str,Any]:
    cfg=cfg or get_config();symbol=_canonical(underlying);local=StrategyConfig(**{**cfg.__dict__,"underlying":symbol});bars=await (_kite_bars_for_underlying(uid,symbol,f"{cfg.interval_minutes}m") if cfg.data_source=="kite" else _truedata_bars_for_underlying(symbol,str(cfg.interval_minutes)))
    if not bars:return {"underlying":symbol,"status":"no_data","signal":None,"trade":None}
    signal=generate_signal(bars,local);result={"underlying":symbol,"status":"signal" if signal.direction!="NONE" else "watching","signal":signal.to_dict(),"spot":bars[-1].close,"interval_minutes":cfg.interval_minutes,"data_source":cfg.data_source,"trade":None}
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
    rows.sort(key=lambda r:(r.get("status") not in {"signal","signal_unresolved"},r["underlying"]));return {"enabled":True,"universe":universe,"signals":rows,"signal_count":sum(1 for r in rows if r.get("status") in {"signal","signal_unresolved"}),"data_source":cfg.data_source}