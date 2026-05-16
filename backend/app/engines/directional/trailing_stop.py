import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from app.schemas.market import Candle
from app.core.trading_mode import TrailMode, TradingModeConfig
from app.engines.indicators.atr import compute_atr
import numpy as np


@dataclass
class TrailState:
    mode: TrailMode
    current_stop: float
    highest_seen: float
    lowest_seen: float
    partial_25_done: bool = False
    partial_50_done: bool = False
    breakeven_set: bool = False
    trail_mult: float = 2.0
    # Mode-specific partial thresholds (fraction, e.g. 0.10 = 10%)
    partial_25_pct: float = 0.10
    partial_50_pct: float = 0.20

    def to_json(self) -> str:
        d = asdict(self)
        d["mode"] = self.mode.value
        return json.dumps(d)

    @classmethod
    def from_json(cls, s: str) -> "TrailState":
        d = json.loads(s)
        d["mode"] = TrailMode(d["mode"])
        # Back-compat: older snapshots may lack the new fields
        d.setdefault("partial_25_pct", 0.10)
        d.setdefault("partial_50_pct", 0.20)
        return cls(**d)


@dataclass
class PartialExitSignal:
    close_pct: int
    new_trail_mult: Optional[float]
    reason: str
    partial_ratio: float = 0.25


@dataclass
class TrailUpdate:
    new_stop: float
    partial: Optional[PartialExitSignal]
    stopped_out: bool
    stop_moved: bool
    current_tp: Optional[float] = None   # echoed back unchanged; engine doesn't move TP


class TrailingStopEngine:

    def update(
        self,
        state: TrailState,
        candles: List[Candle],
        st_value: float,
        direction: str,
        entry_price: float,
        mode: TradingModeConfig,
        initial_tp: Optional[float] = None,
    ) -> TrailUpdate:
        if not candles:
            return TrailUpdate(
                new_stop=state.current_stop, partial=None,
                stopped_out=False, stop_moved=False,
                current_tp=initial_tp,
            )

        current    = candles[-1].close
        prev_stop  = state.current_stop

        h     = np.array([c.high  for c in candles], dtype=np.float64)
        l     = np.array([c.low   for c in candles], dtype=np.float64)
        c_arr = np.array([c.close for c in candles], dtype=np.float64)
        atr_arr = compute_atr(h, l, c_arr, 14)
        atr = float(atr_arr[-1]) if len(atr_arr) > 0 and atr_arr[-1] > 0 else abs(current * 0.01)

        # Update high/low watermark
        if direction == "bullish":
            state.highest_seen = max(state.highest_seen, current)
        else:
            state.lowest_seen = min(state.lowest_seen, current)

        # Advance the stop
        if state.mode == TrailMode.ATR:
            if direction == "bullish":
                candidate = state.highest_seen - atr * state.trail_mult
                state.current_stop = max(state.current_stop, candidate)
            else:
                candidate = state.lowest_seen + atr * state.trail_mult
                state.current_stop = min(state.current_stop, candidate)

        elif state.mode == TrailMode.SUPERTREND:
            if direction == "bullish":
                state.current_stop = max(state.current_stop, st_value)
            else:
                state.current_stop = min(state.current_stop, st_value)

        elif state.mode == TrailMode.PERCENTAGE:
            pct = mode.trail_pct / 100.0
            if direction == "bullish":
                candidate = state.highest_seen * (1.0 - pct)
                state.current_stop = max(state.current_stop, candidate)
            else:
                candidate = state.lowest_seen * (1.0 + pct)
                state.current_stop = min(state.current_stop, candidate)

        partial = self._check_partial(state, entry_price, current, direction)

        if direction == "bullish":
            stopped = candles[-1].low <= state.current_stop
        else:
            stopped = candles[-1].high >= state.current_stop

        return TrailUpdate(
            new_stop=round(state.current_stop, 4),
            partial=partial,
            stopped_out=stopped,
            stop_moved=(round(state.current_stop, 4) != round(prev_stop, 4)),
            current_tp=initial_tp,
        )

    def _check_partial(
        self,
        state: TrailState,
        entry: float,
        current: float,
        direction: str,
    ) -> Optional[PartialExitSignal]:
        if entry <= 0:
            return None

        gain = (current - entry) / entry if direction == "bullish" else (entry - current) / entry

        # First partial: mode-defined threshold (e.g. 5% scalp, 10% swing, 15% positional)
        if gain >= state.partial_25_pct and not state.partial_25_done:
            state.partial_25_done = True
            state.breakeven_set   = True
            # Move stop to breakeven
            if direction == "bullish":
                state.current_stop = max(state.current_stop, entry)
            else:
                state.current_stop = min(state.current_stop, entry)
            return PartialExitSignal(
                close_pct=25,
                new_trail_mult=None,
                reason=f"{state.partial_25_pct*100:.0f}% gain — 25% closed, stop → breakeven",
                partial_ratio=0.25,
            )

        # Second partial: tighten trail multiplier
        if gain >= state.partial_50_pct and not state.partial_50_done:
            state.partial_50_done = True
            state.trail_mult = max(state.trail_mult - 0.5, 1.0)
            return PartialExitSignal(
                close_pct=25,
                new_trail_mult=state.trail_mult,
                reason=f"{state.partial_50_pct*100:.0f}% gain — 25% more closed, trail tightened to {state.trail_mult:.1f}×",
                partial_ratio=0.25,
            )

        # Ride stop: lock in +10% above entry once 30%+ gain reached
        lock_pct = state.partial_50_pct * 1.5
        if gain >= lock_pct and state.partial_50_done:
            lock_price = entry * 1.10 if direction == "bullish" else entry * 0.90
            if direction == "bullish":
                state.current_stop = max(state.current_stop, lock_price)
            else:
                state.current_stop = min(state.current_stop, lock_price)
            return PartialExitSignal(
                close_pct=0,
                new_trail_mult=None,
                reason=f"{lock_pct*100:.0f}% gain — stop locked at +10% from entry, riding",
                partial_ratio=0.0,
            )

        return None
