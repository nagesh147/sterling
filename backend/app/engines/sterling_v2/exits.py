"""Lever 3 -- ATR trailing exit policy (trailing + breakeven), no lookahead.

`atr_trailing` ratchets a stop using only the PREVIOUS bar's extremes, so the
stop level applied during bar i is fully determined by data available before
bar i opens. `TrailingExit` is a thin wrapper that lets the harness drive the
policy through a single `exit_policy` hook (it exposes `init_state(stop)` and is
callable with the trailing signature).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrailState:
    stop: float
    moved_be: bool = False


def atr_trailing(prev_high: float, prev_low: float, entry: float, atr0: float,
                 side: int, state: TrailState, trail_mult: float = 1.5,
                 be_at_r: float = 1.0) -> float:
    """Update the trailing stop using only the PREVIOUS bar's extremes (no
    lookahead). Pulls to breakeven once price has moved be_at_r * atr0 in favor,
    then trails trail_mult * atr0 behind the running extreme. Never loosens."""
    if side == 1:
        if not state.moved_be and prev_high >= entry + be_at_r * atr0:
            state.stop = max(state.stop, entry)
            state.moved_be = True
        state.stop = max(state.stop, prev_high - trail_mult * atr0)
    else:
        if not state.moved_be and prev_low <= entry - be_at_r * atr0:
            state.stop = min(state.stop, entry)
            state.moved_be = True
        state.stop = min(state.stop, prev_low + trail_mult * atr0)
    return state.stop


class TrailingExit:
    """Harness-facing wrapper around `atr_trailing`. One object per backtest;
    the harness calls `init_state(initial_stop)` at each entry and then invokes
    the instance per in-position bar."""

    def __init__(self, trail_mult: float = 1.5, be_at_r: float = 1.0):
        self.trail_mult = trail_mult
        self.be_at_r = be_at_r

    def init_state(self, initial_stop: float) -> TrailState:
        return TrailState(stop=initial_stop)

    def __call__(self, prev_high: float, prev_low: float, entry: float,
                 atr0: float, side: int, state: TrailState) -> float:
        return atr_trailing(prev_high, prev_low, entry, atr0, side, state,
                            trail_mult=self.trail_mult, be_at_r=self.be_at_r)
