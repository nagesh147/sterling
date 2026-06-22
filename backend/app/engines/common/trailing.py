"""Shared trailing stop logic for unification.

Kite uses 3 ST lines for adaptive best-green trail.
General directional uses ATR/TrailState.

This provides common helpers for computing trail from multi-line indicators (e.g. STs),
and can be extended for ATR.

Used to share logic between kite engine and directional trailing.
"""
from typing import Dict, List, Literal, Optional
from dataclasses import dataclass

Direction = Literal["long", "short"]


def best_green_trail(lines: Dict[str, List[float]], direction: Direction, i: int) -> float:
    """
    Given dict of line_name -> values list (e.g. {'fast': [...], 'mid':...}),
    return the tightest still-green line value at index i.
    For long: green = positive trend, tighter = higher value.
    Mirrors regime.best_trail_line_value
    """
    if direction == "long":
        want = 1
        # prefer tightest green (fast if green, else mid, else slow)
        for name in ("fast", "mid", "slow"):
            if name in lines and lines[name][i] > 0:  # assuming positive for green in context
                # in ST, the line value is the trail price when trend matches
                return float(lines[name][i])
        return 0.0
    else:
        want = -1
        for name in ("fast", "mid", "slow"):
            if name in lines and lines[name][i] < 0:
                return float(lines[name][i])
        return 0.0


def ratchet_trail(current_stop: float, new_trail: float, direction: Direction) -> float:
    """Ratchet only in favorable direction."""
    if direction == "long":
        return max(current_stop, new_trail)
    else:
        return min(current_stop, new_trail)


@dataclass
class HybridTrailConfig:
    atr_mult: float = 2.0
    st_weight: float = 0.5  # blend ATR and ST
    use_st_lines: bool = True


class HybridTrailEngine:
    """Full ATR + ST hybrid trail engine for unification.
    Combines ATR-based distance with ST line levels for adaptive trailing.
    Can be used by both directional (ATR primary) and kite (ST primary) paths.
    """
    def __init__(self, config: Optional[HybridTrailConfig] = None):
        self.config = config or HybridTrailConfig()

    def compute_hybrid_trail(self, atr_trail: float, st_lines: Dict[str, float], 
                             direction: Direction, price: float) -> float:
        """Blend ATR trail and best ST green line."""
        if not self.config.use_st_lines:
            return atr_trail
        st_trail = best_green_trail({k: [v] for k, v in st_lines.items()}, direction, 0)
        if st_trail <= 0:
            return atr_trail
        # weighted blend
        if direction == "long":
            blended = max(atr_trail, st_trail) * (1 - self.config.st_weight) + st_trail * self.config.st_weight
            return max(price - (price - blended) * self.config.st_weight, atr_trail)  # favor tighter
        else:
            blended = min(atr_trail, st_trail) * (1 - self.config.st_weight) + st_trail * self.config.st_weight
            return min(price + (blended - price) * self.config.st_weight, atr_trail)
