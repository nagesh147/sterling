"""Independent validation primitives for automated NIFTY ORB option buying.

Pure deterministic helpers. They never invent option prices or place orders.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Callable, Iterable, Sequence

@dataclass(frozen=True)
class TradingCosts:
    brokerage: float = 20.0
    stt_rate: float = 0.000625
    exchange_rate: float = 0.0000297
    sebi_rate: float = 0.000001
    gst_rate: float = 0.18
    stamp_rate: float = 0.00003
    slippage_per_share: float = 0.0

    def round_trip(self, buy_value: float, sell_value: float, quantity: int) -> float:
        turnover = max(0.0, buy_value) + max(0.0, sell_value)
        brokerage = min(self.brokerage, 0.0003 * turnover) * 2 if turnover else 0.0
        stt = max(0.0, sell_value) * self.stt_rate
        exchange = turnover * self.exchange_rate
        sebi = turnover * self.sebi_rate
        stamp = max(0.0, buy_value) * self.stamp_rate
        gst = (brokerage + exchange + sebi) * self.gst_rate
        slippage = max(0, quantity) * self.slippage_per_share * 2
        return brokerage + stt + exchange + sebi + stamp + gst + slippage

@dataclass(frozen=True)
class OptionTrade:
    entry: float
    exit: float
    quantity: int
    direction: str = "BUY"
    max_adverse: float | None = None
    regime: str = "UNKNOWN"
    expiry_dte: int | None = None

@dataclass(frozen=True)
class ValidationResult:
    metrics: dict
    trades: int
    warnings: tuple[str, ...] = ()


def validate_option_trades(trades: Sequence[OptionTrade], costs: TradingCosts = TradingCosts()) -> ValidationResult:
    pnls=[]
    for t in trades:
        if t.direction != "BUY": raise ValueError("ORB validation accepts option buying only")
        if t.quantity <= 0 or t.entry <= 0 or t.exit < 0: raise ValueError("Invalid option trade")
        if t.max_adverse is not None and not isfinite(t.max_adverse): raise ValueError("Invalid adverse excursion")
        gross=(t.exit-t.entry)*t.quantity
        pnls.append(gross-costs.round_trip(t.entry*t.quantity,t.exit*t.quantity,t.quantity))
    wins=[x for x in pnls if x>0]; losses=[x for x in pnls if x<0]
    gross_profit=sum(wins); gross_loss=abs(sum(losses)); equity=peak=max_dd=0.0
    for pnl in pnls:
        equity+=pnl; peak=max(peak,equity); max_dd=max(max_dd,peak-equity)
    return ValidationResult({
        "trades":len(pnls),"wins":len(wins),"losses":len(losses),
        "win_rate":len(wins)/len(pnls) if pnls else 0.0,"net_pnl":sum(pnls),
        "gross_profit":gross_profit,"gross_loss":gross_loss,
        "profit_factor":gross_profit/gross_loss if gross_loss else (float("inf") if gross_profit else 0.0),
        "expectancy":mean(pnls) if pnls else 0.0,"max_drawdown":max_dd,
        "average_win":mean(wins) if wins else 0.0,"average_loss":mean(losses) if losses else 0.0,
        "cost_model":costs.__dict__},len(pnls),("fewer than 30 trades: metrics are statistically weak",) if len(pnls)<30 else ())


def regime_metrics(trades: Sequence[OptionTrade], costs: TradingCosts = TradingCosts()) -> dict[str,dict]:
    groups={}
    for t in trades: groups.setdefault(t.regime.upper(),[]).append(t)
    return {k:validate_option_trades(v,costs).metrics for k,v in sorted(groups.items())}


def expiry_metrics(trades: Sequence[OptionTrade], costs: TradingCosts = TradingCosts()) -> dict[str,dict]:
    groups={"expiry_day":[],"non_expiry":[]}
    for t in trades: groups["expiry_day" if t.expiry_dte==0 else "non_expiry"].append(t)
    return {k:validate_option_trades(v,costs).metrics for k,v in groups.items() if v}


def walk_forward(observations: Sequence, evaluator: Callable[[Sequence,Sequence],dict], *, train_size:int, test_size:int, step:int|None=None) -> list[dict]:
    if train_size<=0 or test_size<=0: raise ValueError("train_size and test_size must be positive")
    step=step or test_size
    if step<=0: raise ValueError("step must be positive")
    results=[]; start=0
    while start+train_size+test_size<=len(observations):
        train=observations[start:start+train_size]; test=observations[start+train_size:start+train_size+test_size]
        result=evaluator(train,test)
        if not isinstance(result,dict): raise TypeError("walk-forward evaluator must return a dict")
        results.append({"train_start":start,"train_end":start+train_size,"test_start":start+train_size,"test_end":start+train_size+test_size,**result})
        start+=step
    if not results: raise ValueError("insufficient observations for requested walk-forward windows")
    return results


def parameter_sensitivity(observations: Sequence, parameter_grid: Sequence[dict], evaluator: Callable[[Sequence,dict],dict]) -> list[dict]:
    if not parameter_grid: raise ValueError("parameter_grid cannot be empty")
    out=[]
    for params in parameter_grid:
        result=evaluator(observations,dict(params))
        if not isinstance(result,dict): raise TypeError("parameter evaluator must return a dict")
        out.append({"parameters":dict(params),**result})
    return out


def require_historical_option_fields(rows: Iterable[dict]) -> None:
    required={"timestamp","symbol","option_type","expiry","strike","open","high","low","close"}
    missing=set(); count=0
    for row in rows: count+=1; missing |= required-set(row)
    if not count: raise ValueError("historical option dataset is empty")
    if missing: raise ValueError(f"historical option dataset missing fields: {', '.join(sorted(missing))}")
