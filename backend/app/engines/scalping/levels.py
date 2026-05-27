"""4H support/resistance level detection.

Pivots are local extrema (high/low) over a lookback window. Nearby pivots
are clustered into horizontal zones. Each zone is scored by its touch count
and recency. Returned as a sorted list of `SupportResistanceLevel`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray

from app.engines.scalping.config import ScalpingProfile as ScalpingConfig


@dataclass
class Level:
    price: float
    touches: int
    first_touch_ts: int
    last_touch_ts: int
    level_type: str  # "support" or "resistance"


def detect_levels(
    highs: NDArray[np.float64],
    lows: NDArray[np.float64],
    closes: NDArray[np.float64],
    timestamps: NDArray[np.int64],
    cfg: ScalpingConfig,
) -> List[Level]:
    """Detect horizontal support/resistance levels from 4H candles.

    1. Find pivot highs and pivot lows (local extrema over a window).
    2. Cluster nearby pivots within `level_tolerance_pct` into zones.
    3. Filter zones with >= `level_touches` touches.
    4. Classify as support (below current price) or resistance (above).
    """
    n = len(closes)
    if n < 10:
        return []

    window = 5
    tolerance = cfg.level_tolerance_pct / 100.0

    pivot_highs: List[Tuple[float, int]] = []
    pivot_lows: List[Tuple[float, int]] = []

    for i in range(window, n - window):
        h_slice = highs[i - window:i + window + 1]
        l_slice = lows[i - window:i + window + 1]
        if np.argmax(h_slice) == window:
            pivot_highs.append((float(highs[i]), int(timestamps[i])))
        if np.argmin(l_slice) == window:
            pivot_lows.append((float(lows[i]), int(timestamps[i])))

    all_pivots = [(p, "high", ts) for p, ts in pivot_highs] + [(p, "low", ts) for p, ts in pivot_lows]
    all_pivots.sort(key=lambda x: x[0])

    if not all_pivots:
        return []

    clusters: List[List[Tuple[float, str, int]]] = []
    cur_cluster = [all_pivots[0]]
    for pivot in all_pivots[1:]:
        mid = np.mean([p[0] for p in cur_cluster])
        if abs(pivot[0] - mid) <= mid * tolerance:
            cur_cluster.append(pivot)
        else:
            clusters.append(cur_cluster)
            cur_cluster = [pivot]
    clusters.append(cur_cluster)

    current_price = float(closes[-1])
    levels: List[Level] = []

    for cluster in clusters:
        touches = len(cluster)
        if touches < cfg.level_touches:
            continue
        prices = [p[0] for p in cluster]
        timestamps_in_cluster = [p[2] for p in cluster]
        level_price = float(np.mean(prices))
        level_type = "support" if level_price < current_price else "resistance"
        levels.append(Level(
            price=round(level_price, 4),
            touches=touches,
            first_touch_ts=min(timestamps_in_cluster),
            last_touch_ts=max(timestamps_in_cluster),
            level_type=level_type,
        ))

    levels.sort(key=lambda l: abs(l.price - current_price))
    return levels


def nearest_level(
    price: float,
    levels: List[Level],
    level_type: str = "",
) -> Level | None:
    """Return the nearest level to price, optionally filtered by type."""
    candidates = levels
    if level_type:
        candidates = [l for l in levels if l.level_type == level_type]
    if not candidates:
        return None
    return min(candidates, key=lambda l: abs(l.price - price))


def price_near_level(
    price: float,
    levels: List[Level],
    tolerance_pct: float = 2.0,
) -> Level | None:
    """Check if price is within tolerance_pct of any level. Returns the closest level or None."""
    if not levels:
        return None
    tolerance = price * (tolerance_pct / 100.0)
    nearby = [(l, abs(l.price - price)) for l in levels if abs(l.price - price) <= tolerance]
    if not nearby:
        return None
    nearby.sort(key=lambda x: x[1])
    return nearby[0][0]