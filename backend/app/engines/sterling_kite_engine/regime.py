"""Pure Sterling Kite Engine regime core — no I/O, no broker types.

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
from app.engines.sterling_kite_engine.config import TrailTarget, SterlingKiteEngineConfig


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

    def red_line_count(self, direction: str, i: int) -> int:
        """Count how many ST lines are red (against the position) at bar ``i``.

        For a long position, red = trend == -1.
        For a short position, red = trend == +1.
        """
        against = -1 if direction == "long" else 1
        count = 0
        if int(self.t_fast[i]) == against:
            count += 1
        if int(self.t_mid[i]) == against:
            count += 1
        if int(self.t_slow[i]) == against:
            count += 1
        return count

    def green_lines(self, direction: str, i: int) -> list:
        """Return the names of ST lines that are still green (aligned with position) at bar ``i``.

        For a long: green = trend == +1. Returns in priority order: slow (widest), mid, fast (tightest).
        The widest still-green line provides the best trailing stop.
        """
        want = 1 if direction == "long" else -1
        lines = []
        # Order: slow (widest/loosest), mid, fast (tightest) — so we can trail
        # the widest available green line for maximum protection without premature exit.
        if int(self.t_slow[i]) == want:
            lines.append("slow")
        if int(self.t_mid[i]) == want:
            lines.append("mid")
        if int(self.t_fast[i]) == want:
            lines.append("fast")
        return lines

    def best_trail_line_value(self, direction: str, i: int) -> float:
        """Return the trail value from the tightest still-green ST line at bar ``i``.

        While all three are green the stop rides the tightest band (``fast``). As the
        tighter lines flip red, the trail steps OUT to the next still-green, WIDER
        line (``fast``→``mid``→``slow``) — i.e. it LOOSENS, to give the trade room to
        run to a multi-line (``two_red``/``three_red``) exit. If no line is green,
        returns 0.0 (all red — an exit should already have fired).

        CAVEAT: the live stop is ratcheted monotonically (``positions.update_stop``
        take-max for a long), which REJECTS this loosening — so in production the
        premium stop stays pinned near the peak ``fast`` level and the red-count exit
        is largely pre-empted (effective exit ≈ ``one_red``). Reconcile the ratchet
        with this stepping-out before relying on ``two_red``+.
        """
        green = self.green_lines(direction, i)
        if not green:
            return 0.0
        # Use the TIGHTEST (innermost) green line as the trail. For a long,
        # tighter = higher stop. "fast" is tightest, then "mid", then "slow".
        # green_lines returns slow→mid→fast, so the last element is the tightest.
        tightest = green[-1]
        return float(self.line(tightest)[i])


def compute_regime(opens, highs, lows, closes, cfg: SterlingKiteEngineConfig) -> RegimeSeries:
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
