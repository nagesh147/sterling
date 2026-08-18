"""Independent ORB Momentum Options strategy.

This strategy intentionally has no dependency on SuperTrend or Adaptive Edge.
It consumes only the underlying OHLCV stream and its own configurable rules,
then produces an option trade candidate.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, time
from statistics import mean
from typing import Literal, Sequence

Direction = Literal["LONG", "SHORT", "NONE"]

@dataclass(frozen=True)
class ORBMomentumConfig:
    enabled: bool = True
    universe: str = "FNO"
    interval_minutes: int = 5
    opening_range_minutes: int = 15
    entry_start: str = "09:30"
    entry_end: str = "12:00"
    breakout_atr: float = 0.15
    atr_period: int = 14
    volume_multiplier: float = 1.15
    vwap_slope_bars: int = 3
    structure_lookback: int = 3
    option_moneyness: str = "ATM"
    option_steps_itm: int = 1
    expiry_selection: str = "NEAREST"
    max_risk_inr: float = 3000.0
    max_trades_per_day: int = 3
    max_signals_per_day: int = 10
    avoid_expiry_day: bool = False
    paper_only: bool = True
    data_source: str = "kite"
    execution_broker: str = "kite"

@dataclass(frozen=True)
class UnderlyingBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

@dataclass(frozen=True)
class ORBSignal:
    symbol: str
    timestamp: datetime
    direction: Direction
    opening_range_high: float
    opening_range_low: float
    vwap: float
    atr: float
    volume_ratio: float
    breakout_distance: float
    reason: str

    def to_dict(self) -> dict:
        d = asdict(self); d["timestamp"] = self.timestamp.isoformat(); return d

@dataclass(frozen=True)
class OptionCandidate:
    symbol: str
    option_type: Literal["CE", "PE"]
    strike: float
    expiry: str
    ltp: float
    bid: float
    ask: float
    lot_size: int
    volume: float = 0.0
    open_interest: float = 0.0

@dataclass(frozen=True)
class ORBTradeSignal:
    underlying: str
    direction: Direction
    option: OptionCandidate
    timestamp: datetime
    entry: float
    stop: float
    target: float
    risk_inr: float
    quantity: int
    reason: str

    def to_dict(self) -> dict:
        d = asdict(self); d["timestamp"] = self.timestamp.isoformat(); return d

def _atr(bars: Sequence[UnderlyingBar], period: int) -> float:
    if len(bars) < period + 1: return 0.0
    trs = [max(b.high-b.low, abs(b.high-p.close), abs(b.low-p.close)) for p,b in zip(bars[-period-1:-1], bars[-period:])]
    return mean(trs)

def _vwap(bars: Sequence[UnderlyingBar]) -> float:
    total = pv = 0.0
    for b in bars:
        typical = (b.high+b.low+b.close)/3
        pv += typical * max(b.volume, 0); total += max(b.volume, 0)
    return pv/total if total else bars[-1].close

def _opening_range(bars: Sequence[UnderlyingBar], minutes: int) -> tuple[float,float] | None:
    if not bars: return None
    session = [b for b in bars if b.timestamp.time() >= time(9,15) and b.timestamp.time() < time(9,15+minutes)]
    return (max(b.high for b in session), min(b.low for b in session)) if session else None

def generate_signal(symbol: str, bars: Sequence[UnderlyingBar], cfg: ORBMomentumConfig) -> ORBSignal:
    if not bars: raise ValueError("bars cannot be empty")
    b = bars[-1]; rng = _opening_range(bars, cfg.opening_range_minutes); atr = _atr(bars, cfg.atr_period); vwap = _vwap([x for x in bars if x.timestamp.date()==b.timestamp.date()])
    if rng is None: return ORBSignal(symbol,b.timestamp,"NONE",0,0,vwap,atr,0,0,"opening range unavailable")
    hi,lo=rng; baseline=[x.volume for x in bars[-20:-1] if x.volume>0]; vr=b.volume/(mean(baseline) if baseline else b.volume or 1)
    inside=time.fromisoformat(cfg.entry_start) <= b.timestamp.time() <= time.fromisoformat(cfg.entry_end)
    if not inside or atr<=0: return ORBSignal(symbol,b.timestamp,"NONE",hi,lo,vwap,atr,vr,0,"outside entry window or ATR unavailable")
    if b.close > hi + cfg.breakout_atr*atr and b.close > vwap and vr >= cfg.volume_multiplier:
        return ORBSignal(symbol,b.timestamp,"LONG",hi,lo,vwap,atr,vr,b.close-hi,"opening-range upside breakout with VWAP and volume confirmation")
    if b.close < lo - cfg.breakout_atr*atr and b.close < vwap and vr >= cfg.volume_multiplier:
        return ORBSignal(symbol,b.timestamp,"SHORT",hi,lo,vwap,atr,vr,lo-b.close,"opening-range downside breakout with VWAP and volume confirmation")
    return ORBSignal(symbol,b.timestamp,"NONE",hi,lo,vwap,atr,vr,0,"conditions not satisfied")

def select_option(underlying: float, direction: Direction, contracts: Sequence[OptionCandidate], cfg: ORBMomentumConfig) -> OptionCandidate | None:
    if direction == "NONE": return None
    wanted = "CE" if direction == "LONG" else "PE"
    pool=[c for c in contracts if c.option_type==wanted and c.ltp>0 and c.ask>=0]
    if not pool:return None
    nearest=min(pool,key=lambda c:c.strike if direction=="LONG" else -c.strike)
    if cfg.option_moneyness.upper()=="ATM": return min(pool,key=lambda c:abs(c.strike-underlying))
    atm=min(pool,key=lambda c:abs(c.strike-underlying)); step=sorted(pool,key=lambda c:abs(c.strike-atm.strike))
    if cfg.option_moneyness.upper()=="ITM":
        target=underlying-cfg.option_steps_itm*50 if direction=="LONG" else underlying+cfg.option_steps_itm*50
        return min(pool,key=lambda c:abs(c.strike-target))
    return nearest

def build_trade_signal(signal: ORBSignal, option: OptionCandidate, cfg: ORBMomentumConfig) -> ORBTradeSignal:
    entry=option.ask if option.ask>0 else option.ltp; risk_per_unit=max(signal.atr*0.10, entry*0.15); max_qty=max(1,int(cfg.max_risk_inr/risk_per_unit)); quantity=max(option.lot_size,(max_qty//option.lot_size)*option.lot_size); quantity=min(quantity, option.lot_size*max(1,int(cfg.max_risk_inr/(risk_per_unit*option.lot_size))))
    stop=max(0.05,entry-risk_per_unit); target=entry+2*(entry-stop)
    return ORBTradeSignal(signal.symbol,signal.direction,option,signal.timestamp,entry,stop,target,(entry-stop)*quantity,quantity,signal.reason)
