"""Runtime orchestration for NIFTY ORB + VWAP options."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from app.engines.nifty_orb_options import Bar, OptionContract, StrategyConfig, build_trade_plan, generate_signal, select_option, summarize_pnl
from app.core.config import settings
_IST=timezone(timedelta(hours=5,minutes=30)); _CONFIG_KEY="nifty_orb_options_config"; _TRADE_STATE_PREFIX="nifty_orb_options_trade_state:"

def get_config()->StrategyConfig:
    d=StrategyConfig(enabled=False)
    try:
        from app.services import db
        raw=db.get_config(_CONFIG_KEY)
        if raw:
            x=json.loads(raw) if isinstance(raw,str) else raw
            return StrategyConfig(**{k:v for k,v in {**d.__dict__,**x}.items() if k in StrategyConfig.__dataclass_fields__})
    except Exception: pass
    return d

def set_config(values:dict[str,Any])->StrategyConfig:
    c=get_config().__dict__.copy(); bad=sorted(set(values)-set(c))
    if bad: raise ValueError(f"Unknown NIFTY ORB config fields: {', '.join(bad)}")
    c.update(values)
    if c["data_source"] not in {"kite","truedata"}: raise ValueError("data_source must be 'kite' or 'truedata'")
    if c["execution_broker"]!="kite": raise ValueError("execution_broker is fixed to 'kite'")
    if c["interval_minutes"] not in {1,3,5,10,15}: raise ValueError("interval_minutes must be one of 1, 3, 5, 10, 15")
    if c["opening_range_minutes"] not in {5,10,15,20,30}: raise ValueError("opening_range_minutes must be one of 5, 10, 15, 20, 30")
    if c["entry_start"]>=c["entry_end"]: raise ValueError("entry_start must be before entry_end")
    if c["max_trades_per_day"]<1: raise ValueError("max_trades_per_day must be >= 1")
    if c["max_risk_inr"]<=0: raise ValueError("max_risk_inr must be > 0")
    if not 0<c["max_spread_pct"]<=10: raise ValueError("max_spread_pct must be > 0 and <= 10")
    if c["min_option_volume"]<0 or c["min_open_interest"]<0: raise ValueError("option liquidity thresholds cannot be negative")
    if c["expiry_selection"] not in {"nearest","weekly","monthly"}: raise ValueError("expiry_selection must be nearest, weekly or monthly")
    if c["expiry_dte_min"]<0 or c["expiry_dte_max"]<c["expiry_dte_min"]: raise ValueError("invalid expiry DTE bounds")
    if c["avoid_expiry_day"] and c["expiry_dte_max"]==0: raise ValueError("avoid_expiry_day cannot be enabled with expiry_dte_max=0")
    if c["data_source"]=="truedata" and c["truedata_use_quote_freshness"] and not c["truedata_use_ticks"]: raise ValueError("truedata_use_quote_freshness requires truedata_use_ticks")
    cfg=StrategyConfig(**c)
    from app.services import db
    db.set_config(_CONFIG_KEY,json.dumps(cfg.__dict__,separators=(",",":"))); return cfg

def _bar(r:Any)->Bar:
    ts=r.get("timestamp") or r.get("time") or r.get("timestamp_ms")
    if isinstance(ts,(int,float)): dt=datetime.fromtimestamp(float(ts)/1000,tz=_IST)
    elif isinstance(ts,datetime): dt=ts if ts.tzinfo else ts.replace(tzinfo=_IST); dt=dt.astimezone(_IST)
    else:
        s=str(ts).replace("Z","+00:00"); dt=datetime.fromisoformat(s) if "T" in s or "+" in s[10:] else datetime.strptime(s,"%Y-%m-%d %H:%M:%S").replace(tzinfo=_IST); dt=dt.astimezone(_IST)
    return Bar(dt,float(r["open"]),float(r["high"]),float(r["low"]),float(r["close"]),float(r.get("volume") or 0))

def normalize_option_chain(rows:Any,expiry:str|None=None)->list[OptionContract]:
    if isinstance(rows,dict): rows=rows.get("Records") or rows.get("records") or rows.get("data") or rows.get("options") or []
    out=[]
    for r in rows or []:
        if not isinstance(r,dict): continue
        raw=str(r.get("option_type") or r.get("type") or r.get("opttype") or "").upper(); typ={"CALL":"CE","C":"CE","PUT":"PE","P":"PE"}.get(raw,raw)
        if typ not in {"CE","PE"}: continue
        try: strike=float(r.get("strike") or r.get("strike_price"))
        except (TypeError,ValueError): continue
        out.append(OptionContract(str(r.get("symbol") or r.get("tradingsymbol") or r.get("instrument") or ""),strike,str(r.get("expiry") or r.get("expiry_date") or expiry or "")[:10],typ,float(r.get("ltp") or r.get("last_price") or r.get("close") or 0),float(r.get("bid") or r.get("bid_price") or 0),float(r.get("ask") or r.get("ask_price") or 0),int(r.get("lot_size") or r.get("lotsize") or 75),float(r["delta"]) if r.get("delta") not in (None,"") else None,float(r.get("volume") or 0),float(r.get("oi") or r.get("open_interest") or 0)))
    return out

async def _kite_bars(uid:str,interval:str)->list[Bar]:
    from app.services.exchanges.kite import accounts as ka
    from app.services.exchanges import instrument_registry as reg
    acct=ka.get_active(uid)
    if not acct: raise RuntimeError("No active Kite account")
    client=await ka.acquire_client(acct); inst=reg.get_instrument("NIFTY") or reg.get_instrument("NIFTY 50")
    if not inst: raise RuntimeError("NIFTY instrument is not registered")
    rows=await client.get_candles(inst,interval,limit=240); now=datetime.now(_IST); minutes=int(interval.rstrip("m"))
    return [b for b in [_bar({"timestamp_ms":r.timestamp_ms,"open":r.open,"high":r.high,"low":r.low,"close":r.close,"volume":r.volume}) for r in rows] if b.timestamp+timedelta(minutes=minutes)<=now]

async def _kite_options(uid:str,direction:str)->list[OptionContract]:
    from app.services.exchanges.kite import accounts as ka
    acct=ka.get_active(uid)
    if not acct: raise RuntimeError("No active Kite account")
    cfg=get_config(); client=await ka.acquire_client(acct); rows=await client.search_instruments("NIFTY","NFO",limit=5000); today=datetime.now(_IST).date(); wanted="CE" if direction=="LONG" else "PE"; candidates=[]
    for r in rows:
        if str(r.get("name") or "").upper()!="NIFTY" or str(r.get("instrument_type") or "").upper()!=wanted: continue
        try: exp=datetime.strptime(str(r.get("expiry"))[:10],"%Y-%m-%d").date()
        except (TypeError,ValueError): continue
        dte=(exp-today).days
        if cfg.expiry_dte_min<=dte<=cfg.expiry_dte_max and not (cfg.avoid_expiry_day and dte==0): candidates.append((exp,r))
    if not candidates:return []
    if cfg.expiry_selection=="monthly":
        month=min((e.year,e.month) for e,_ in candidates); expiry=max(e for e,_ in candidates if (e.year,e.month)==month)
    else: expiry=min(e for e,_ in candidates)
    out=[]
    for exp,r in candidates:
        if exp!=expiry:continue
        sym=str(r.get("tradingsymbol") or "")
        try:
            q=await client.get_quote([f"NFO:{sym}"]); d=q.get(f"NFO:{sym}",{}) or {}; dep=d.get("depth") or {}; buy=(dep.get("buy") or [{}])[0]; sell=(dep.get("sell") or [{}])[0]
            out.append(OptionContract(sym,float(r.get("strike") or 0),exp.isoformat(),wanted,float(d.get("last_price") or 0),float(buy.get("price") or 0),float(sell.get("price") or 0),int(r.get("lot_size") or 1),None,float(d.get("volume") or 0),float(d.get("oi") or 0)))
        except Exception: continue
    return out

async def snapshot(uid:str)->dict[str,Any]:
    cfg=get_config()
    if not cfg.enabled:return {"enabled":False,"signal":None,"plan":None,"data_source":cfg.data_source}
    if cfg.data_source=="kite":
        bars=await _kite_bars(uid,f"{cfg.interval_minutes}m"); signal=generate_signal(bars,cfg,as_of=datetime.now(_IST)); contracts=await _kite_options(uid,signal.direction) if signal.direction!="NONE" else []
    else:
        from app.services.market_data.truedata import TrueDataHistoricalClient
        from app.services.providers.truedata.orb_provider import TrueDataOrbProvider
        client=TrueDataHistoricalClient(settings.truedata_username,settings.truedata_password,timeout=settings.truedata_timeout_seconds)
        try:
            provider=TrueDataOrbProvider(client); bars=await provider.bars("NIFTY 50",cfg); signal=generate_signal(bars,cfg,as_of=datetime.now(_IST)); contracts=await provider.option_chain("NIFTY",cfg.expiry_selection,cfg) if signal.direction!="NONE" else []
        finally: await client.aclose()
    plan=None
    if signal.direction!="NONE":
        option=select_option(bars[-1].close,signal.direction,contracts,cfg); plan=build_trade_plan(signal,option,cfg,spot=bars[-1].close)
    return {"enabled":True,"data_source":cfg.data_source,"execution_broker":cfg.execution_broker,"signal":signal.to_dict(),"plan":plan.to_dict() if plan else None}

def _trade_state(uid:str)->dict:
    from app.services import db
    try:
        raw=db.get_config(_TRADE_STATE_PREFIX+uid); return json.loads(raw) if raw else {"date":"","count":0,"signals":[]}
    except Exception:return {"date":"","count":0,"signals":[]}

def _save_trade_state(uid:str,state:dict)->None:
    from app.services import db; db.set_config(_TRADE_STATE_PREFIX+uid,json.dumps(state,separators=(",",":")))

def _today_trade_state(uid:str)->dict:
    state=_trade_state(uid); today=datetime.now(_IST).date().isoformat()
    if state.get("date")!=today: state={"date":today,"count":0,"signals":[]}
    return state

def backtest_from_bars(rows:list[dict[str,Any]],cfg:StrategyConfig|None=None)->dict[str,Any]:
    """Underlying baseline. Positions are strictly non-overlapping and reset per session."""
    cfg=cfg or get_config(); bars=[_bar(r) for r in rows]
    if len(bars)<100:return {"metrics":summarize_pnl([]),"warning":"At least 100 bars are required"}
    pnls=[]; i=60; day_counts={}
    while i<len(bars):
        day=bars[i].timestamp.date(); count=day_counts.get(day,0)
        if count>=cfg.max_trades_per_day: i+=1; continue
        sig=generate_signal(bars[:i+1],cfg)
        if sig.direction=="NONE" or sig.atr<=0: i+=1; continue
        entry=bars[i].close; risk=max(sig.atr*cfg.stop_buffer_atr,1e-9); stop=entry-risk if sig.direction=="LONG" else entry+risk; target=entry+risk*cfg.target_r if sig.direction=="LONG" else entry-risk*cfg.target_r; outcome=None; j=i+1
        while j<len(bars) and bars[j].timestamp.date()==day:
            b=bars[j]
            if sig.direction=="LONG":
                if b.low<=stop: outcome=-risk; break
                if b.high>=target: outcome=target-entry; break
            else:
                if b.high>=stop: outcome=-risk; break
                if b.low<=target: outcome=entry-target; break
            j+=1
        if outcome is not None:
            pnls.append(outcome); day_counts[day]=count+1; i=j+1
        else:
            i=max(i+1,j)
    return {"metrics":{**summarize_pnl(pnls),"model":"underlying-point baseline","costs_included":False,"option_pnl":False},"warning":"Underlying baseline only. Option-level replay requires historical option premiums, contracts, costs and slippage."}

async def execute_auto(uid:str)->dict[str,Any]:
    cfg=get_config()
    if not cfg.enabled:return {"status":"disabled"}
    from app.services.kite_engine import state as engine_state, positions
    from app.services import live_safety
    from app.services.exchanges.kite import accounts as ka
    universal=engine_state.get_config(uid)
    if not getattr(universal,"auto_execute",False):return {"status":"advisory"}
    acct=ka.get_active(uid)
    if not acct:return {"status":"blocked","reason":"No active Kite account"}
    state=_today_trade_state(uid)
    if int(state["count"])>=cfg.max_trades_per_day:return {"status":"daily_limit","count":state["count"]}
    if any(p.status in (positions.OPEN,positions.PENDING) and str(p.underlying).upper() in {"NIFTY","NIFTY 50"} for p in positions.open_positions(uid)):return {"status":"position_exists"}
    snap=await snapshot(uid); plan=snap.get("plan") or {}; signal=snap.get("signal") or {}; contract=plan.get("contract") or {}; symbol=str(contract.get("symbol") or ""); qty=int(plan.get("quantity") or 0)
    if not symbol or qty<=0:return {"status":"no_trade_plan","signal":signal}
    signal_key=f"{signal.get('timestamp')}:{signal.get('direction')}:{symbol}"
    if signal_key in set(state.get("signals",[])):return {"status":"duplicate_signal"}
    if cfg.avoid_expiry_day and str(contract.get("expiry") or "")[:10]==datetime.now(_IST).date().isoformat():return {"status":"expiry_day_blocked"}
    idem=live_safety.make_idempotency_key(uid,signal_key,"BUY")
    decision=live_safety.assert_safe_to_trade(positions=[],idempotency_key=idem,check_daily_loss=False)
    if not decision.allowed and decision.code!="duplicate_order":return {"status":"blocked","reason":decision.reason,"code":decision.code}
    if live_safety.check_idempotency(idem):return {"status":"duplicate_order"}
    client=await ka.acquire_client(acct)
    try:
        orders=await client.get_orders(); existing=next((o for o in orders if str(o.get("tag") or "")==idem),None)
    except Exception: existing=None
    if existing:
        oid=str(existing.get("order_id") or "")
    else:
        rows=await client.search_instruments("NIFTY","NFO",limit=5000); inst=next((r for r in rows if str(r.get("tradingsymbol") or "").upper()==symbol.upper()),None)
        if not inst:return {"status":"blocked","reason":f"Kite contract {symbol} is unavailable"}
        try: result=await client.place_order_option(symbol,"buy",qty,exchange="NFO",tag=idem)
        except Exception as exc:return {"status":"error","message":str(exc)}
        oid=str((result or {}).get("order_id") or "")
        if not oid:return {"status":"error","message":"Broker returned no order id"}
        live_safety.record_idempotency(idem,oid)
    if not oid:return {"status":"error","message":"Existing broker order has no id"}
    try:
        history=await client.get_order_history(oid); latest=history[-1] if isinstance(history,list) and history else (history if isinstance(history,dict) else {})
        filled=int(float(latest.get("filled_quantity") or 0)); avg=float(latest.get("average_price") or 0)
    except Exception: filled,avg=qty,float(plan.get("entry_premium") or 0)
    if filled<=0: filled=qty
    if avg<=0: avg=float(plan.get("entry_premium") or 0)
    rows=await client.search_instruments("NIFTY","NFO",limit=5000); inst=next((r for r in rows if str(r.get("tradingsymbol") or "").upper()==symbol.upper()),None)
    if not inst:return {"status":"blocked","reason":"Cannot resolve filled contract for protection"}
    from app.services.kite_engine import protection
    direction="long" if signal.get("direction")=="LONG" else "short"
    armed=await protection.arm_position(client,uid,symbol=symbol,exchange="NFO",token=int(inst.get("instrument_token") or 0),qty=filled,lot_size=int(contract.get("lot_size") or 1),entry_premium=avg,stop_premium=float(plan.get("stop_premium") or 0),order_id=oid,stop_mode=universal.stop_mode,direction="long",signal_direction=direction,vehicle="otm_options",underlying="NIFTY",exit_mode=universal.exit_mode,entry_spot=float(plan.get("underlying_entry") or 0),entry_delta=float(abs(contract.get("delta") or 0.5)),strike=float(contract.get("strike") or 0),expiry=str(contract.get("expiry") or "")[:10],target_premium=float(plan.get("target_premium") or 0))
    state["count"]=int(state["count"])+1; state.setdefault("signals",[]).append(signal_key); _save_trade_state(uid,state)
    return {"status":"executed","order_id":oid,"symbol":symbol,"quantity":filled,"requested_quantity":qty,"fill_price":avg,"plan":plan,"protection":armed.describe(),"protected":armed.protected}

async def execute_manual(uid:str)->dict[str,Any]:
    cfg=get_config()
    if not cfg.enabled:raise ValueError("NIFTY ORB strategy is disabled")
    snap=await snapshot(uid); plan=snap.get("plan") or {}; contract=plan.get("contract") or {}; qty=int(plan.get("quantity") or 0)
    if not contract.get("symbol") or qty<=0:raise ValueError("No executable NIFTY ORB trade plan is active")
    from app.services.kite_engine.service import place_manual_order
    return {"plan":plan,"execution":await place_manual_order(uid,contract["symbol"],"BUY",qty,exchange="NFO")}
