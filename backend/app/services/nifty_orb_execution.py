"""Execution adapter for the independent ORB strategy.

The ORB engine produces BUY-only option plans. This module owns execution reconciliation
and protection; Trading Mode remains the universal Paper/Live + Manual/Auto owner.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any
_IST=timezone(timedelta(hours=5,minutes=30))

def _state(uid:str)->dict[str,Any]:
    from app.services import db
    import json
    try: raw=db.get_config(f"nifty_orb_options_trade_state:{uid}"); state=json.loads(raw) if raw else {}
    except Exception: state={}
    today=datetime.now(_IST).date().isoformat()
    if state.get("date")!=today: state={"date":today,"count":0,"signals":[]}
    return state

def _save_state(uid:str,state:dict[str,Any])->None:
    from app.services import db
    import json
    db.set_config(f"nifty_orb_options_trade_state:{uid}",json.dumps(state,separators=(",",":")))

async def _find_contract(client,symbol:str,underlying:str)->tuple[str|None,dict|None]:
    for exchange in ("NFO","BFO"):
        try: rows=await client.search_instruments(underlying,exchange,limit=10000)
        except Exception: continue
        for row in rows:
            if str(row.get("tradingsymbol") or "").upper()==symbol.upper(): return exchange,row
    return None,None

async def _existing_order_by_tag(client,tag:str)->dict|None:
    try: orders=await client.get_orders()
    except Exception: return None
    return next((o for o in orders or [] if str(o.get("tag") or "")==tag),None)

async def _resolve_fill(client,order_id:str,*,timeout_s:float=3.0)->tuple[int,float,str]:
    deadline=asyncio.get_running_loop().time()+timeout_s
    while True:
        latest={}
        try:
            history=await client.get_order_history(order_id)
            latest=history[-1] if isinstance(history,list) and history else (history if isinstance(history,dict) else {})
        except Exception: pass
        status=str(latest.get("status") or "").upper(); filled=int(float(latest.get("filled_quantity") or latest.get("filled_qty") or 0)); avg=float(latest.get("average_price") or latest.get("average_price_filled") or 0)
        if not filled:
            try:
                trades=await client.get_order_trades(order_id)
                if trades:
                    filled=sum(int(float(t.get("quantity") or 0)) for t in trades); value=sum(float(t.get("quantity") or 0)*float(t.get("average_price") or t.get("price") or 0) for t in trades); avg=value/filled if filled else avg
            except Exception: pass
        if status in {"COMPLETE","PARTIALLY FILLED","PARTIAL","CANCELLED","REJECTED"} or filled>0:return filled,avg,status
        if asyncio.get_running_loop().time()>=deadline:return filled,avg,status or "UNKNOWN"
        await asyncio.sleep(0.25)

async def _cancel_unfilled_remainder(client,order_id:str)->None:
    try: await client.cancel_order(order_id)
    except Exception: pass

async def execute_scan(uid:str,*,scan:dict[str,Any],max_trades:int)->dict[str,Any]:
    """Execute only scanner-produced BUY plans; never recompute a signal at execution time."""
    from app.services.kite_engine import state as engine_state, positions, protection
    from app.services import live_safety
    from app.services.exchanges.kite import accounts
    universal=engine_state.get_config(uid)
    if not getattr(universal,"auto_execute",False):return {"status":"advisory","executed":[]}
    account=accounts.get_active(uid)
    if not account:return {"status":"blocked","reason":"No active Kite account","executed":[]}
    trade_state=_state(uid)
    if int(trade_state.get("count",0))>=max_trades:return {"status":"daily_limit","executed":[],"count":trade_state["count"]}
    client=await accounts.acquire_client(account); executed=[]
    seen_underlyings={str(p.underlying).upper() for p in positions.open_positions(uid) if p.status in (positions.OPEN,positions.PENDING)}
    for row in scan.get("signals",[]):
        if row.get("status")!="signal":continue
        plan=row.get("trade") or {}; contract=plan.get("contract") or {}; symbol=str(contract.get("symbol") or ""); underlying=str(row.get("underlying") or "").upper(); requested_quantity=int(plan.get("quantity") or 0)
        if not symbol or requested_quantity<=0 or not underlying or underlying in seen_underlyings:continue
        if len(executed)+int(trade_state.get("count",0))>=max_trades:break
        signal=row.get("signal") or {}; signal_key=f"{underlying}:{signal.get('timestamp')}:{signal.get('direction')}:{symbol}"
        if signal_key in set(trade_state.get("signals",[])):continue
        idem=live_safety.make_idempotency_key(uid,signal_key,"BUY")
        decision=live_safety.assert_safe_to_trade(positions=[],idempotency_key=idem,check_daily_loss=False)
        if not decision.allowed and decision.code!="duplicate_order":
            executed.append({"status":"blocked","underlying":underlying,"symbol":symbol,"reason":decision.reason}); continue
        if live_safety.check_idempotency(idem):continue
        existing=await _existing_order_by_tag(client,idem)
        if existing: order_id=str(existing.get("order_id") or "")
        else:
            exchange,instrument=await _find_contract(client,symbol,underlying)
            if not exchange or not instrument:continue
            try: order=await client.place_order_option(symbol,"buy",requested_quantity,exchange=exchange,tag=idem)
            except Exception as exc:
                executed.append({"status":"error","underlying":underlying,"symbol":symbol,"error":str(exc)});continue
            order_id=str((order or {}).get("order_id") or "")
            if not order_id:
                executed.append({"status":"error","underlying":underlying,"symbol":symbol,"error":"Broker returned no order id"});continue
            live_safety.record_idempotency(idem,order_id)
        if not order_id:continue
        exchange,instrument=await _find_contract(client,symbol,underlying)
        if not exchange or not instrument:continue
        filled_qty,fill_price,broker_status=await _resolve_fill(client,order_id)
        if filled_qty<=0:
            if broker_status not in {"CANCELLED","REJECTED"}:await _cancel_unfilled_remainder(client,order_id)
            executed.append({"status":"pending_or_unfilled","underlying":underlying,"symbol":symbol,"order_id":order_id,"broker_status":broker_status});continue
        if filled_qty<requested_quantity:await _cancel_unfilled_remainder(client,order_id)
        held=positions.get(uid,symbol)
        if held is not None and held.status in (positions.OPEN,positions.PENDING) and held.order_id==order_id and held.gtt_id:
            protected=True; protection_note=f"existing protection #{held.gtt_id}"
        else:
            try:
                armed=await protection.arm_position(client,uid,symbol=symbol,exchange=exchange,token=int(instrument.get("instrument_token") or 0),qty=filled_qty,lot_size=int(contract.get("lot_size") or instrument.get("lot_size") or 1),entry_premium=fill_price or float(plan.get("entry_premium") or 0),stop_premium=float(plan.get("stop_premium") or 0),order_id=order_id,stop_mode=universal.stop_mode,direction="long",signal_direction="long" if signal.get("direction")=="LONG" else "short",vehicle="otm_options",underlying=underlying,exit_mode=universal.exit_mode,entry_spot=float(plan.get("underlying_entry") or row.get("spot") or 0),entry_delta=float(abs(contract.get("delta") or 0.5)),strike=float(contract.get("strike") or 0),expiry=str(contract.get("expiry") or "")[:10],target_premium=float(plan.get("target_premium") or 0))
                protected=bool(armed.protected); protection_note=armed.describe()
            except Exception as exc:
                protected=False; protection_note=f"arming failed: {exc}"
        trade_state["count"]=int(trade_state.get("count",0))+1; trade_state.setdefault("signals",[]).append(signal_key); seen_underlyings.add(underlying)
        executed.append({"status":"executed","underlying":underlying,"symbol":symbol,"quantity":filled_qty,"requested_quantity":requested_quantity,"fill_price":fill_price,"broker_status":broker_status,"order_id":order_id,"protected":protected,"protection":protection_note,"plan":plan})
    _save_state(uid,trade_state)
    return {"status":"executed" if executed else "no_trade","executed":executed,"count":trade_state["count"]}
