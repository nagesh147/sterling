"""Regime-adaptive ATR stop multiplier.

Pure function — no I/O. A fixed ATR stop multiple (e.g. 2.0×ATR) treats every
volatility regime the same. But ATR's own distribution shifts: a 2.0×ATR stop
that breathes fine in a calm regime gets wicked out when realized vol is at the
top of its recent range. This scales the multiplier by the *percentile rank* of
the current ATR within its recent history:

  rank 0.5 (median regime)  → base_mult unchanged
  rank → 1.0 (turbulent)    → widen toward base_mult * hi_scale
  rank → 0.0 (quiet)        → tighten toward base_mult * lo_scale

The result is clamped to [min_mult, max_mult] so it can never run away, and
falls back to base_mult when there isn't enough history to judge the regime.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

_MIN_HISTORY = 10


def _percentile_rank(x: float, hist: np.ndarray) -> float:
    """Fraction of `hist` below x, counting ties at half-weight → in [0, 1]."""
    n = hist.size
    below = float(np.count_nonzero(hist < x))
    equal = float(np.count_nonzero(hist == x))
    return (below + 0.5 * equal) / n


def regime_atr_multiplier(
    atr_now: float,
    atr_history: Sequence[float],
    base_mult: float,
    *,
    lo_scale: float = 0.8,
    hi_scale: float = 1.3,
    min_mult: float = 0.5,
    max_mult: float = 6.0,
) -> float:
    """Scale `base_mult` by the volatility regime (ATR percentile rank).

    lo_scale/hi_scale bound how far the multiplier moves at the extremes of the
    ATR range; min_mult/max_mult are hard clamps on the returned multiple.
    """
    hist = np.asarray([float(a) for a in atr_history], dtype=np.float64)
    hist = hist[np.isfinite(hist)]
    if hist.size < _MIN_HISTORY or not np.isfinite(atr_now):
        return base_mult

    rank = _percentile_rank(float(atr_now), hist)  # 0..1, 0.5 = median regime
    if rank >= 0.5:
        factor = 1.0 + (hi_scale - 1.0) * (rank - 0.5) / 0.5
    else:
        factor = lo_scale + (1.0 - lo_scale) * (rank / 0.5)

    return float(min(max_mult, max(min_mult, base_mult * factor)))
