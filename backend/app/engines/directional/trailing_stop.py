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

    def to_json(self) -> str:
        d = asdict(self)
        d["mode"] = self.mode.value
        return json.dumps(d)

    @classmethod
    def from_json(cls, s: str) -> "TrailState":
        d = json.loads(s)
        d["mode"] = TrailMode(d["mode"])
        return cls(**d)


@dataclass
class PartialExitSignal:
    close_pct: int
    new_trail_mult: Optional[float]
    reason: str


@dataclass
class TrailUpdate:
    new_stop: float
    partial: Optional[PartialExitSignal]
    stopped_out: bool
    stop_moved: bool


class TrailingStopEngine:

    def update(
        self,
        state: TrailState,
        candles: List[Candle],
        st_value: float,
        direction: str,
        entry_price: float,
        mode: TradingModeConfig,
    ) -> TrailUpdate:
        if not candles:
            return TrailUpdate(
                new_stop=state.current_stop, partial=None,
                stopped_out=False, stop_moved=False,
            )

        current = candles[-1].close
        prev_stop = state.current_stop

        h = np.array([c.high for c in candles], dtype=np.float64)
        l = np.array([c.low for c in candles], dtype=np.float64)
        c_arr = np.array([c.close for c in candles], dtype=np.float64)
        atr_arr = compute_atr(h, l, c_arr, 14)
        atr = float(atr_arr[-1]) if atr_arr[-1] > 0 else abs(current * 0.01)

        if direction == "bullish":
            state.highest_seen = max(state.highest_seen, current)
        else:
            state.lowest_seen = min(state.lowest_seen, current)

        if state.mode == TrailMode.ATR:
            if direction == "bullish":
                new = state.highest_seen - atr * state.trail_mult
                state.current_stop = max(state.current_stop, new)
            else:
                new = state.lowest_seen + atr * state.trail_mult
                state.current_stop = min(state.current_stop, new)

        elif state.mode == TrailMode.SUPERTREND:
            if direction == "bullish":
                state.current_stop = max(state.current_stop, st_value)
            else:
                state.current_stop = min(state.current_stop, st_value)

        elif state.mode == TrailMode.PERCENTAGE:
            pct = mode.trail_pct / 100.0
            if direction == "bullish":
                new = state.highest_seen * (1.0 - pct)
                state.current_stop = max(state.current_stop, new)
            else:
                new = state.lowest_seen * (1.0 + pct)
                state.current_stop = min(state.current_stop, new)

        partial = self._check_partial(state, entry_price, current, direction)

        if direction == "bullish":
            stopped = candles[-1].low <= state.current_stop
        else:
            stopped = candles[-1].high >= state.current_stop

        return TrailUpdate(
            new_stop=state.current_stop,
            partial=partial,
            stopped_out=stopped,
            stop_moved=(state.current_stop != prev_stop),
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

        if direction == "bullish":
            gain = (current - entry) / entry
        else:
            gain = (entry - current) / entry

        if gain >= 0.10 and not state.partial_25_done:
            state.partial_25_done = True
            state.breakeven_set = True
            if direction == "bullish":
                state.current_stop = max(state.current_stop, entry)
            else:
                state.current_stop = min(state.current_stop, entry)
            return PartialExitSignal(
                close_pct=25,
                new_trail_mult=None,
                reason="10% gain — 25% closed, stop → breakeven",
            )

        if gain >= 0.20 and not state.partial_50_done:
            state.partial_50_done = True
            state.trail_mult = max(state.trail_mult - 0.5, 1.0)
            return PartialExitSignal(
                close_pct=25,
                new_trail_mult=state.trail_mult,
                reason="20% gain — 25% more closed, trail tightened",
            )

        if gain >= 0.30 and state.partial_50_done:
            if direction == "bullish":
                state.current_stop = max(state.current_stop, entry * 1.10)
            else:
                state.current_stop = min(state.current_stop, entry * 0.90)
            return PartialExitSignal(
                close_pct=0,
                new_trail_mult=None,
                reason="30% gain — stop locked at +10%, riding",
            )

        return None
