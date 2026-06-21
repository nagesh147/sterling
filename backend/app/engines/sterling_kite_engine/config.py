"""Knobs for the 1H Heikin-Ashi Sterling Kite Engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

TrailTarget = Literal["fast", "mid", "slow"]


@dataclass(frozen=True)
class SterlingKiteEngineConfig:
    """Configuration for the Sterling Kite Engine.

    ``fast``/``mid``/``slow`` are named by flip-responsiveness (driven by the
    multiplier), matching the source spec. Each is a ``(period, multiplier)``
    pair, verbatim from the spec.
    """

    fast: Tuple[int, float] = (21, 1.0)
    mid: Tuple[int, float] = (14, 2.0)
    slow: Tuple[int, float] = (7, 3.0)
    # Which ST line trails the stop / triggers the exit flip. ``fast`` (the tightest
    # band, mult 1.0) is the most robust choice in the 7.5y IS/OOS sweep: stripped of
    # the options wrapper it is OOS-positive on 4/4 indices, vs 3/4 for ``mid`` and
    # 0/4 for ``slow`` (study/kite_st_exit_analysis.md). A tighter trail also banks
    # the move faster → less theta bleed on long options.
    trail_target: TrailTarget = "fast"
    # Removed from the live engine + UI + API (provably inert: 0.0 P&L change across
    # 7.5y — it keyed off the slow/widest ST, which always flips after the trail has
    # already exited). Retained here ONLY so the offline study scripts that documented
    # this can still construct the config; the live exit is the trail_target flip.
    early_lock: bool = False
    early_lock_profit_r: float = 1.0

    @property
    def warmup(self) -> int:
        """Bars to skip before all three SuperTrends are valid."""
        return max(self.fast[0], self.mid[0], self.slow[0])

    def params(self, target: TrailTarget) -> Tuple[int, float]:
        return {"fast": self.fast, "mid": self.mid, "slow": self.slow}[target]
