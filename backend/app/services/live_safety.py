"""Fail-closed live execution safety primitives."""
from __future__ import annotations
import hashlib,time,uuid
from dataclasses import dataclass,field
from typing import Any,Dict,List,Optional

_KILL_SWITCH={"enabled":False,"reason":"","set_ts_ms":0}; _IDEMPOTENCY_CACHE={}; _IDEMPOTENCY_TTL_MS=60000; _RETRY_QUEUE={}

def kill_switch_state(): return dict(_KILL_SWITCH)
def set_kill_switch(enabled:bool,reason:str=""):
    _KILL_SWITCH.update({"enabled":bool(enabled),"reason":reason or ("manual halt" if enabled else ""),"set_ts_ms":int(time.time()*1000)}); return dict(_KILL_SWITCH)

@dataclass
class DailyLossConfig:
    enabled:bool=True
    soft_warn_inr:float=-1000.0
    hard_halt_inr:float=-1500.0
    soft_warn_usd:Optional[float]=None
    hard_halt_usd:Optional[float]=None
    def __post_init__(self):
        if self.soft_warn_usd is not None:self.soft_warn_inr=float(self.soft_warn_usd)
        if self.hard_halt_usd is not None:self.hard_halt_inr=float(self.hard_halt_usd)
        if self.hard_halt_inr>=0 or self.soft_warn_inr>=0 or self.soft_warn_inr<self.hard_halt_inr:raise ValueError("daily-loss thresholds must be negative with soft_warn >= hard_halt")
_DAILY_LOSS_CFG=DailyLossConfig()

def configure_daily_loss(cfg):
    global _DAILY_LOSS_CFG; _DAILY_LOSS_CFG=cfg

def _today_start_ms_ist():
    from datetime import datetime,timezone,timedelta
    ist=timezone(timedelta(hours=5,minutes=30)); n=datetime.now(ist); return int(n.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()*1000)

def daily_realized_pnl_inr(positions):
    """Today's realised P&L across the supplied positions.

    The field cascade ends at ``realized_pnl_usd`` because paper/crypto positions
    expose *only* that field. Omitting it made every such position contribute
    0.00, so the daily-loss breaker read "clear" no matter how much the book had
    lost -- a realised -600 against a -500 halt threshold was allowed through. A
    risk read that cannot see a loss must not be treated as no loss.

    The threshold is whatever ``DailyLossConfig`` was given (it already accepts
    either ``*_inr`` or ``*_usd`` and stores one number), so a book must be
    configured in its own currency. Mixed-currency books need separate
    thresholds; that is a pre-existing limitation of the single-threshold config,
    not something this cascade can resolve.
    """
    total=0.0; start=_today_start_ms_ist()
    for p in positions:
        ts=getattr(p,"exit_timestamp_ms",None) or getattr(p,"closed_ms",None)
        pnl=getattr(p,"realized_pnl_inr",None)
        if pnl is None:pnl=getattr(p,"realized_pnl",None)
        if pnl is None:pnl=getattr(p,"realized_pnl_usd",None)
        if ts and pnl is not None and int(ts)>=start:total+=float(pnl)
    return round(total,2)

def daily_realized_pnl(positions):
    total=0.0
    for p in positions:
        ts=getattr(p,"exit_timestamp_ms",None) or getattr(p,"closed_ms",None); pnl=getattr(p,"realized_pnl_usd",None)
        if ts and pnl is not None and int(ts)>=_today_start_ms_ist():total+=float(pnl)
    return round(total,2)

def _account_daily_pnl_inr(uid:str|None)->float|None:
    if not uid:return None
    from app.services.kite_engine import state
    # The strict accessor deliberately propagates DB/JSON failures. A failed risk-state
    # read must never be interpreted as a zero loss and allow a new live order.
    return float(state.daily_realized_pnl_strict(uid))

def daily_loss_state(positions=None, *, uid:str|None=None):
    pnl=_account_daily_pnl_inr(uid) if uid else daily_realized_pnl_inr(positions or [])
    level="clear"
    if _DAILY_LOSS_CFG.enabled:
        if pnl<=_DAILY_LOSS_CFG.hard_halt_inr:level="halt"
        elif pnl<=_DAILY_LOSS_CFG.soft_warn_inr:level="warning"
    return {"pnl_inr":pnl,"pnl_usd":pnl,"level":level,"enabled":_DAILY_LOSS_CFG.enabled,"soft_warn_inr":_DAILY_LOSS_CFG.soft_warn_inr,"hard_halt_inr":_DAILY_LOSS_CFG.hard_halt_inr,"soft_warn_usd":_DAILY_LOSS_CFG.soft_warn_inr,"hard_halt_usd":_DAILY_LOSS_CFG.hard_halt_inr}

def make_idempotency_key(*parts):return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:32]
def check_idempotency(key):
    if not key:return None
    e=_IDEMPOTENCY_CACHE.get(key)
    if not e:return None
    if int(time.time()*1000)-e[0]>_IDEMPOTENCY_TTL_MS:_IDEMPOTENCY_CACHE.pop(key,None);return None
    return e[1]
def record_idempotency(key,order_id):
    if key:_IDEMPOTENCY_CACHE[key]=(int(time.time()*1000),order_id)

@dataclass
class RetryItem:
    id:str; payload:Dict[str,Any]; attempt:int=0; max_attempts:int=3; last_error:str=""; enqueued_ms:int=field(default_factory=lambda:int(time.time()*1000)); last_attempt_ms:int=0; poison:bool=False

def enqueue_retry(payload,error,max_attempts=3):
    x=RetryItem(uuid.uuid4().hex[:10].upper(),dict(payload),0,max_attempts,error);_RETRY_QUEUE[x.id]=x;return x
def list_retries(include_poison=True):return sorted(list(_RETRY_QUEUE.values()) if include_poison else [x for x in _RETRY_QUEUE.values() if not x.poison],key=lambda x:x.enqueued_ms)
def mark_attempt(rid,error=""):
    x=_RETRY_QUEUE.get(rid)
    if not x:return None
    x.attempt+=1;x.last_attempt_ms=int(time.time()*1000);x.last_error=error;x.poison=x.attempt>=x.max_attempts;return x
def remove_retry(rid):return _RETRY_QUEUE.pop(rid,None) is not None
def clear_retries():_RETRY_QUEUE.clear()

@dataclass
class SafetyDecision:
    allowed:bool; reason:str=""; code:str=""
    def to_dict(self):return {"allowed":self.allowed,"reason":self.reason,"code":self.code}

def assert_safe_to_trade(positions,idempotency_key=None,*,check_daily_loss=True,uid:str|None=None):
    try:
        if kill_switch_state().get("enabled"):return SafetyDecision(False,f"Kill switch active: {kill_switch_state().get('reason') or 'manual halt'}","kill_switch")
        if check_daily_loss:
            dl=daily_loss_state(positions,uid=uid)
            if dl["level"]=="halt":return SafetyDecision(False,f"Daily loss circuit breaker: INR {dl['pnl_inr']:.2f} <= INR {dl['hard_halt_inr']:.2f}","daily_loss_halt")
        if idempotency_key:
            prior=check_idempotency(idempotency_key)
            if prior:return SafetyDecision(False,f"Duplicate order — already placed as {prior}","duplicate_order")
        return SafetyDecision(True)
    except Exception as exc:return SafetyDecision(False,f"Safety evaluation failed closed: {exc}","safety_unknown")

@dataclass
class PerSymbolCapConfig:max_per_symbol:int=3
_PER_SYMBOL_CFG=PerSymbolCapConfig()
def configure_per_symbol_cap(cfg):
    global _PER_SYMBOL_CFG;_PER_SYMBOL_CFG=cfg
def open_count_for_symbol(positions,sym):
    n=0
    for p in positions:
        s=getattr(getattr(p,"status",None),"value",getattr(p,"status",None))
        if s in ("open","partially_closed","pending") and str(getattr(p,"underlying","")).upper()==sym.upper():n+=1
    return n
def per_symbol_cap_breach(sym,positions):
    n=open_count_for_symbol(positions,sym);return f"per-symbol cap reached: {n}/{_PER_SYMBOL_CFG.max_per_symbol} open on {sym.upper()}" if n>=_PER_SYMBOL_CFG.max_per_symbol else None

def reset_all_for_tests():
    _KILL_SWITCH.update({"enabled":False,"reason":"","set_ts_ms":0});_IDEMPOTENCY_CACHE.clear();_RETRY_QUEUE.clear()
    global _DAILY_LOSS_CFG;_DAILY_LOSS_CFG=DailyLossConfig()
