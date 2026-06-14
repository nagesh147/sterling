"""Pure triple-SuperTrend regime core — no I/O, no broker types.

Heikin-Ashi conversion -> three SuperTrends -> per-bar bull/bear/flat regime,
fresh full-alignment entry transitions, and the trail line/trend selected by the
configured ``trail_target``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
from numpy.typing import NDArray

from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend
from app.engines.triple_supertrend.config import TrailTarget, TripleSupertrendConfig


@dataclass
class RegimeSeries:
    bull: NDArray[np.bool_]
    bear: NDArray[np.bool_]
    t_fast: NDArray[np.int64]
    t_mid: NDArray[np.int64]
    t_slow: NDArray[np.int64]
    l_fast: NDArray[np.float64]
    l_mid: NDArray[np.float64]
    l_slow: NDArray[np.float64]
    warmup: int

    def line(self, target: TrailTarget) -> NDArray[np.float64]:
        return {"fast": self.l_fast, "mid": self.l_mid, "slow": self.l_slow}[target]

    def trend(self, target: TrailTarget) -> NDArray[np.int64]:
        return {"fast": self.t_fast, "mid": self.t_mid, "slow": self.t_slow}[target]


def compute_regime(opens, highs, lows, closes, cfg: TripleSupertrendConfig) -> RegimeSeries:
    o = np.asarray(opens, dtype=float)
    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)
    c = np.asarray(closes, dtype=float)

    _, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)

    l_fast, t_fast = compute_supertrend(ha_h, ha_l, ha_c, cfg.fast[0], cfg.fast[1])
    l_mid, t_mid = compute_supertrend(ha_h, ha_l, ha_c, cfg.mid[0], cfg.mid[1])
    l_slow, t_slow = compute_supertrend(ha_h, ha_l, ha_c, cfg.slow[0], cfg.slow[1])

    valid = np.zeros(len(c), dtype=bool)
    valid[cfg.warmup:] = True  # all three trends seeded by the largest period

    bull = valid & (t_fast == 1) & (t_mid == 1) & (t_slow == 1)
    bear = valid & (t_fast == -1) & (t_mid == -1) & (t_slow == -1)

    return RegimeSeries(
        bull=bull, bear=bear,
        t_fast=t_fast, t_mid=t_mid, t_slow=t_slow,
        l_fast=l_fast, l_mid=l_mid, l_slow=l_slow,
        warmup=cfg.warmup,
    )


def entry_transitions(r: RegimeSeries) -> Tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    """Masks of bars that FRESHLY enter full alignment (not aligned at i-1)."""
    prev_bull = np.concatenate([[False], r.bull[:-1]])
    prev_bear = np.concatenate([[False], r.bear[:-1]])
    longs = r.bull & ~prev_bull
    shorts = r.bear & ~prev_bear
    # need a fully-valid prior bar (avoid the SuperTrend warmup seed flip)
    longs[: r.warmup + 1] = False
    shorts[: r.warmup + 1] = False
    return longs, shorts
