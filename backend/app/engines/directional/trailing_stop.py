"""STRATEGY STUB — trailing-stop logic removed in the strategy reset.

The data containers (`TrailState`, `PartialExitSignal`, `TrailUpdate`) are kept
intact because `paper_store` serialises `TrailState` to/from JSON and positions
depend on that shape. Only the decision logic in `TrailingStopEngine.update`
was stripped (preserved in git history on the `strategy-v2` branch): it now
returns a no-op update that never moves the stop, never exits, and never takes
partials.

Implement the new trailing logic in `TrailingStopEngine.update`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import List, Optional

from app.core.trading_mode import TrailMode, TradingModeConfig
from app.schemas.market import Candle


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
    partial_25_pct: float = 0.10
    partial_50_pct: float = 0.20
    tightening_offset: float = 0.0
    structure_dte: Optional[int] = None

    def to_json(self) -> str:
        d = asdict(self)
        d["mode"] = self.mode.value
        return json.dumps(d)

    @classmethod
    def from_json(cls, s: str) -> "TrailState":
        d = json.loads(s)
        d["mode"] = TrailMode(d["mode"])
        # Back-compat: older snapshots may lack newer fields
        d.setdefault("partial_25_pct", 0.10)
        d.setdefault("partial_50_pct", 0.20)
        d.setdefault("tightening_offset", 0.0)
        d.setdefault("structure_dte", None)
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
    current_tp: Optional[float] = None  # echoed back unchanged


class TrailingStopEngine:
    """STUB — trailing logic removed. `update` never moves the stop or exits."""

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
        """ATR (or %/supertrend) trailing stop with breakeven and a monotonic
        ratchet — the stop only ever moves in the trade's favour, never loosens.

        • Track the best price seen (highest for longs, lowest for shorts).
        • Trail `trail_mult × ATR` behind that extreme.
        • Once price has run one full trail distance in favour, pull the stop to
          breakeven (entry) so a winner can't turn into a loser.
        • `stopped_out` when the live price has reached the (ratcheted) stop.

        Implementing this here activates trailing for every position the monitor
        tracks — scalping included — since `add_position` already attaches a
        TrailState and the background monitor calls this each poll.
        """
        if not candles or len(candles) < 2:
            return TrailUpdate(state.current_stop, None, False, False, initial_tp)

        is_long = str(direction).lower() in ("long", "bullish", "buy")
        price = float(candles[-1].close)
        hi = float(candles[-1].high)
        lo = float(candles[-1].low)

        # ── ATR over the available candles ──────────────────────────────────
        period = min(14, len(candles) - 1)
        trs = []
        for k in range(len(candles) - period, len(candles)):
            h, l, pc = float(candles[k].high), float(candles[k].low), float(candles[k - 1].close)
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr = sum(trs) / len(trs) if trs else 0.0

        mult = state.trail_mult or getattr(mode, "trail_atr_mult", 2.0) or 2.0
        if state.mode == TrailMode.PERCENTAGE:
            trail_dist = price * (mult / 100.0)
        else:
            trail_dist = mult * atr if atr > 0 else price * 0.01
        if trail_dist <= 0:
            trail_dist = price * 0.01

        # ── Track the favourable extreme ────────────────────────────────────
        state.highest_seen = max(state.highest_seen or price, hi, price)
        prior_low = state.lowest_seen if (state.lowest_seen and state.lowest_seen > 0) else price
        state.lowest_seen = min(prior_low, lo, price)

        new_stop = state.current_stop
        moved = False

        if is_long:
            cand = state.highest_seen - trail_dist
            if state.mode == TrailMode.SUPERTREND and st_value and st_value > 0:
                cand = max(cand, float(st_value))
            if not state.breakeven_set and price >= entry_price + trail_dist:
                cand = max(cand, entry_price)            # lock to breakeven
                state.breakeven_set = True
            if cand > new_stop:                          # ratchet up only
                new_stop, moved = cand, True
            stopped = price <= new_stop
        else:
            cand = state.lowest_seen + trail_dist
            if state.mode == TrailMode.SUPERTREND and st_value and st_value > 0:
                cand = min(cand, float(st_value))
            if not state.breakeven_set and price <= entry_price - trail_dist:
                cand = min(cand, entry_price)            # lock to breakeven
                state.breakeven_set = True
            if cand < new_stop:                          # ratchet down only
                new_stop, moved = cand, True
            stopped = price >= new_stop

        state.current_stop = round(float(new_stop), 6)
        return TrailUpdate(
            new_stop=state.current_stop,
            partial=None,
            stopped_out=bool(stopped),
            stop_moved=moved,
            current_tp=initial_tp,
        )
