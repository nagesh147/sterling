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
    trail_target: TrailTarget = "mid"
    early_lock: bool = False
    # Exit on slow-ST flip once unrealized profit >= this * initial risk.
    early_lock_profit_r: float = 1.0

    @property
    def warmup(self) -> int:
        """Bars to skip before all three SuperTrends are valid."""
        return max(self.fast[0], self.mid[0], self.slow[0])

    def params(self, target: TrailTarget) -> Tuple[int, float]:
        return {"fast": self.fast, "mid": self.mid, "slow": self.slow}[target]
