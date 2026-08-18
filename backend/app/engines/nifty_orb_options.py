"""NIFTY opening-range breakout engine with directional option execution planning."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, time
from math import isfinite
from statistics import mean
from typing import Iterable, Literal, Sequence

Direction = Literal["LONG", "SHORT", "NONE"]
Regime = Literal["EXPANSION", "TREND", "RANGE", "UNKNOWN"]


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class StrategyConfig:
    enabled: bool = True
    underlying: str = "NIFTY 50"
    interval_minutes: int = 5
    opening_range_minutes: int = 15
    entry_start: str = "09:30"
    entry_end: str = "12:00"
    min_breakout_atr: float = 0.15
    volume_multiplier: float = 1.15
    vwap_slope_lookback: int = 3
    trend_lookback: int = 5
    atr_period: int = 14
    stop_buffer_atr: float = 0.10
    trail_atr: float = 1.25
    target_r: float = 2.0
    option_moneyness: str = "ATM"
    option_steps_itm: int = 1
    max_risk_inr: float = 3000.0
    max_trades_per_day: int = 2
    avoid_expiry_day: bool = False
    expiry_selection: str = "nearest"
    execution_broker: str = "kite"
    data_source: str = "kite"
    paper_only: bool = True


@dataclass(frozen=True)
class Signal:
    direction: Direction
    regime: Regime
    timestamp: datetime | None
    or_high: float
    or_low: float
    vwap: float
    atr: float
    breakout_distance: float
    volume_ratio: float
    confidence: float
    reason: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat() if self.timestamp else None
        return d


@dataclass(frozen=True)
class OptionContract:
    symbol: str
    strike: float
    expiry: str
    option_type: Literal["CE", "PE"]
    ltp: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    lot_size: int = 1
    delta: float | None = None
    volume: float = 0.0
    open_interest: float = 0.0


@dataclass(frozen=True)
class TradePlan:
    direction: Direction
    option_type: Literal["CE", "PE"]
    contract: OptionContract
    underlying_entry: float
    underlying_stop: float
    initial_risk_points: float
    target_points: float
    quantity: int
    risk_inr: float
    reason: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["contract"] = asdict(self.contract)
        return d


def _typical_price(bar: Bar) -> float:
    return (bar.high + bar.low + bar.close) / 3.0


def vwap(bars: Sequence[Bar]) -> float:
    pv = sum(_typical_price(b) * max(b.volume, 0.0) for b in bars)
    vol = sum(max(b.volume, 0.0) for b in bars)
    return pv / vol if vol > 0 else (bars[-1].close if bars else 0.0)


def atr(bars: Sequence[Bar], period: int = 14) -> float:
    if len(bars) < 2:
        return 0.0
    trs: list[float] = []
    prev = bars[0].close
    for b in bars[1:]:
        trs.append(max(b.high - b.low, abs(b.high - prev), abs(b.low - prev)))
        prev = b.close
    window = trs[-max(1, period):]
    return mean(window) if window else 0.0


def _parse_time(value: str) -> time:
    h, m = value.split(":", 1)
    return time(int(h), int(m))


def _volume_ratio(bars: Sequence[Bar], lookback: int = 20) -> float:
    if not bars:
        return 0.0
    current = max(bars[-1].volume, 0.0)
    prior = [max(b.volume, 0.0) for b in bars[-lookback-1:-1]]
    baseline = mean(prior) if prior else 0.0
    return current / baseline if baseline > 0 else 1.0


def _regime(bars: Sequence[Bar], cfg: StrategyConfig, current_vwap: float, current_atr: float) -> Regime:
    if len(bars) < max(cfg.trend_lookback + 1, 5) or current_atr <= 0:
        return "UNKNOWN"
    recent = bars[-cfg.trend_lookback:]
    net = recent[-1].close - recent[0].close
    efficiency = abs(net) / max(sum(abs(b.close - a.close) for a, b in zip(recent, recent[1:])), 1e-9)
    last_range = recent[-1].high - recent[-1].low
    if last_range >= 1.25 * current_atr and efficiency >= 0.45:
        return "EXPANSION"
    if efficiency >= 0.35 and abs(recent[-1].close - current_vwap) >= 0.25 * current_atr:
        return "TREND"
    return "RANGE"


def opening_range(bars: Sequence[Bar], minutes: int = 15) -> tuple[float, float]:
    if not bars:
        raise ValueError("No bars supplied")
    # Historical fetches contain multiple sessions. ORB must always be built
    # from the latest session represented by the input, never bars[0]'s date.
    session = max(b.timestamp.date() for b in bars)
    tz = next((b.timestamp.tzinfo for b in bars if b.timestamp.date() == session), None)
    start = datetime.combine(session, time(9, 15), tzinfo=tz)
    end = datetime.combine(session, time(9, 15 + minutes // 60, minutes % 60), tzinfo=tz)
    opening = [b for b in bars if start <= b.timestamp < end]
    if not opening:
        raise ValueError("Opening range bars are missing")
    return max(b.high for b in opening), min(b.low for b in opening)


def generate_signal(bars: Sequence[Bar], cfg: StrategyConfig = StrategyConfig()) -> Signal:
    if not bars:
        raise ValueError("No bars supplied")
    or_high, or_low = opening_range(bars, cfg.opening_range_minutes)
    current = bars[-1]
    session_bars = [b for b in bars if b.timestamp.date() == current.timestamp.date() and b.timestamp.time() >= time(9, 15)]
    current_vwap = vwap(session_bars)
    current_atr = atr(bars, cfg.atr_period)
    vol_ratio = _volume_ratio(bars)
    regime = _regime(bars, cfg, current_vwap, current_atr)
    t = current.timestamp.time()
    if not (_parse_time(cfg.entry_start) <= t <= _parse_time(cfg.entry_end)):
        return Signal("NONE", regime, current.timestamp, or_high, or_low, current_vwap, current_atr, 0.0, vol_ratio, 0.0, "outside entry window")
    if current_atr <= 0:
        return Signal("NONE", regime, current.timestamp, or_high, or_low, current_vwap, current_atr, 0.0, vol_ratio, 0.0, "ATR unavailable")
    long_break = current.close - or_high
    short_break = or_low - current.close
    long_ok = long_break >= cfg.min_breakout_atr * current_atr and current.close > current_vwap
    short_ok = short_break >= cfg.min_breakout_atr * current_atr and current.close < current_vwap
    volume_ok = vol_ratio >= cfg.volume_multiplier
    if long_ok and volume_ok and regime in ("EXPANSION", "TREND"):
        confidence = min(0.99, 0.50 + 0.15 * min(long_break / current_atr, 2.0) + 0.10 * min(vol_ratio / cfg.volume_multiplier, 2.0))
        return Signal("LONG", regime, current.timestamp, or_high, or_low, current_vwap, current_atr, long_break, vol_ratio, confidence, "ORB high break + VWAP + momentum + volume")
    if short_ok and volume_ok and regime in ("EXPANSION", "TREND"):
        confidence = min(0.99, 0.50 + 0.15 * min(short_break / current_atr, 2.0) + 0.10 * min(vol_ratio / cfg.volume_multiplier, 2.0))
        return Signal("SHORT", regime, current.timestamp, or_high, or_low, current_vwap, current_atr, short_break, vol_ratio, confidence, "ORB low break + VWAP + momentum + volume")
    return Signal("NONE", regime, current.timestamp, or_high, or_low, current_vwap, current_atr, max(long_break, short_break, 0.0), vol_ratio, 0.0, "filters not aligned")


def select_option(spot: float, direction: Direction, contracts: Sequence[OptionContract], cfg: StrategyConfig) -> OptionContract:
    if direction not in ("LONG", "SHORT"):
        raise ValueError("Cannot select an option without a directional signal")
    typ = "CE" if direction == "LONG" else "PE"
    candidates = [c for c in contracts if c.option_type == typ and c.lot_size > 0 and c.ltp > 0]
    if not candidates:
        raise ValueError(f"No liquid {typ} contracts available")
    strikes = sorted({c.strike for c in candidates})
    atm = min(strikes, key=lambda x: abs(x - spot))
    if cfg.option_moneyness.upper() == "ATM":
        target = atm
    else:
        step = sorted({abs(b - a) for a, b in zip(strikes, strikes[1:]) if b > a})
        increment = step[0] if step else 50.0
        target = atm - cfg.option_steps_itm * increment if direction == "LONG" else atm + cfg.option_steps_itm * increment
    return min(candidates, key=lambda c: (abs(c.strike - target), -c.volume, -c.open_interest))


def build_trade_plan(signal: Signal, option: OptionContract, cfg: StrategyConfig, *, spot: float) -> TradePlan:
    if signal.direction not in ("LONG", "SHORT"):
        raise ValueError("No trade plan for a neutral signal")
    risk_points = max(signal.atr * cfg.stop_buffer_atr, abs(signal.breakout_distance) * 0.50, 1.0)
    stop = spot - risk_points if signal.direction == "LONG" else spot + risk_points
    target = spot + cfg.target_r * risk_points if signal.direction == "LONG" else spot - cfg.target_r * risk_points
    delta = abs(option.delta) if option.delta is not None else 0.50
    premium_risk_per_share = max(risk_points * delta, 0.01)
    lots = int(cfg.max_risk_inr // (premium_risk_per_share * option.lot_size))
    quantity = max(0, lots * option.lot_size)
    risk = quantity * premium_risk_per_share
    return TradePlan(signal.direction, option.option_type, option, spot, stop, risk_points, abs(target - spot), quantity, risk, signal.reason)


def summarize_pnl(pnls: Iterable[float]) -> dict:
    values = [float(x) for x in pnls if isfinite(float(x))]
    wins = [x for x in values if x > 0]
    losses = [x for x in values if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for x in values:
        equity += x
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    expectancy = mean(values) if values else 0.0
    return {
        "trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(values) if values else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0),
        "expectancy": expectancy,
        "average_win": mean(wins) if wins else 0.0,
        "average_loss": mean(losses) if losses else 0.0,
        "max_drawdown": max_dd,
        "net_pnl": sum(values),
    }
