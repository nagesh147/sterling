"""Knobs for the 1H Heikin-Ashi Sterling Kite Engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

from app.engines.common.exit_counter import ExitMode  # shared for unification with directional

TrailTarget = Literal["fast", "mid", "slow"]

# How many red SuperTrend lines trigger an auto-exit.
# Entry = all three lines green + green arrow (fresh full alignment).
# Exit modes are the COUNTER of that entry (see common/exit_counter.py for shared logic):
#   one_red          — exit when ANY one ST line turns red (tightest)
#   two_red          — exit when any TWO ST lines turn red
#   three_red        — exit when ALL THREE ST lines turn red (full reversal)
#   three_red_signal — exit when all three red AND a fresh red arrow (counter-entry)



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
    # ── Auto-exit mode ────────────────────────────────────────────────────────
    # Controls how many SuperTrend lines must turn red before the position exits.
    # "one_red" is the tightest (original behaviour — trail_target flip = one line
    # going red). "three_red_signal" is the loosest (holds until a full counter-entry).
    # The trailing stop rides the BEST still-green line, tightening as lines flip.
    exit_mode: ExitMode = "two_red"  # balanced default: exit on any 2 ST lines red (good room vs protection)
    # Removed from the live engine + UI + API (provably inert: 0.0 P&L change across
    # 7.5y — it keyed off the slow/widest ST, which always flips after the trail has
    # already exited). Retained here ONLY so the offline study scripts that documented
    # this can still construct the config; the live exit is the trail_target flip.
    early_lock: bool = False
    early_lock_profit_r: float = 1.0
    # Hybrid ST weight for ATR+ST blend in trailing (0=pure ATR, 1=pure ST)
    hybrid_st_weight: float = 0.5

    @property
    def warmup(self) -> int:
        """Bars to skip before all three SuperTrends are valid."""
        return max(self.fast[0], self.mid[0], self.slow[0])

    def params(self, target: TrailTarget) -> Tuple[int, float]:
        return {"fast": self.fast, "mid": self.mid, "slow": self.slow}[target]

    @property
    def exit_red_count(self) -> int:
        """Number of red ST lines needed to trigger exit (1, 2, or 3)."""
        from app.engines.common.exit_counter import get_exit_threshold
        return get_exit_threshold(self.exit_mode)

    @property
    def exit_needs_signal(self) -> bool:
        """True when exit_mode = three_red_signal (also requires a fresh counter-arrow)."""
        from app.engines.common.exit_counter import exit_needs_counter_signal
        return exit_needs_counter_signal(self.exit_mode)
