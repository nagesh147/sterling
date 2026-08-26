"""Swing levels on the underlying's own chart.

The source is qualitative here -- "its top will be visible, then from here
rejection, then here too" -- so this module asserts a *specific* mechanical
definition the source only gestured at. That is a real choice and it is stated
rather than buried: a level is a cluster of confirmed swing pivots, and its
strength is how many pivots it holds.

A pivot at bar ``i`` is not knowable until ``i + lookback`` bars have printed.
Every function here takes that seriously, because using an unconfirmed pivot is
lookahead, and stripping lookahead out of a finished backtest has already cost
this codebase one rewrite.
"""
from __future__ import annotations

from typing import Sequence

from .models import Candle, SpotLevel


def swing_pivots(candles: Sequence[Candle], lookback: int) -> tuple[list, list]:
    """(resistance_prices, support_prices) from confirmed pivots only.

    The last ``lookback`` bars are deliberately excluded: their pivots cannot be
    confirmed yet, and including them is how a level appears in a backtest that
    could not have existed in the moment.
    """
    highs, lows = [], []
    n = len(candles)
    for i in range(lookback, n - lookback):
        left = candles[i - lookback:i]
        right = candles[i + 1:i + lookback + 1]
        # Strictly greater on the right, greater-or-equal on the left. A plain
        # `>=` on both sides makes every bar of a flat stretch a pivot, which
        # manufactures a level with dozens of "touches" out of a quiet range --
        # conviction invented from noise. This picks the last bar of a plateau
        # and no others.
        if (candles[i].high >= max(c.high for c in left)
                and candles[i].high > max(c.high for c in right)):
            highs.append((candles[i].high, candles[i].ts_ms))
        if (candles[i].low <= min(c.low for c in left)
                and candles[i].low < min(c.low for c in right)):
            lows.append((candles[i].low, candles[i].ts_ms))
    return highs, lows


def _cluster(points: list, cluster_pct: float, kind: str, min_touches: int) -> list:
    """Merge pivots within ``cluster_pct`` of each other into one level."""
    out: list[SpotLevel] = []
    groups: list[list] = []
    for price, ts in sorted(points):
        if groups and groups[-1][-1][0] > 0 and \
                abs(price - groups[-1][-1][0]) / groups[-1][-1][0] * 100 <= cluster_pct:
            groups[-1].append((price, ts))
        else:
            groups.append([(price, ts)])
    for g in groups:
        if len(g) < min_touches:
            continue
        out.append(SpotLevel(price=sum(p for p, _ in g) / len(g), kind=kind,  # type: ignore[arg-type]
                             touches=len(g), last_touch_ms=max(ts for _, ts in g)))
    return out


def find_levels(candles: Sequence[Candle], *, pivot_lookback: int = 5,
                cluster_pct: float = 0.75, min_touches: int = 2,
                window: int = 120) -> list[SpotLevel]:
    """Every confirmed, clustered level in the trailing ``window`` bars."""
    if len(candles) < pivot_lookback * 2 + 2:
        return []
    seg = list(candles)[-window:] if window > 0 else list(candles)
    highs, lows = swing_pivots(seg, pivot_lookback)
    return (_cluster(highs, cluster_pct, "resistance", min_touches)
            + _cluster(lows, cluster_pct, "support", min_touches))


def live_levels(levels: Sequence[SpotLevel], spot: float,
                proximity_pct: float) -> list[SpotLevel]:
    """Levels spot is currently sitting on, nearest first.

    ``proximity_pct`` is the measured edge in this strategy (45.0% [30.7, 60.2]
    of triggers within 1% reached a 30% favourable excursion, against 21.7%
    [21.5, 21.9] unconditionally). Widening it does not add signals of the same
    quality -- it adds signals of baseline quality.
    """
    if spot <= 0 or proximity_pct <= 0:
        return []
    near = [lv for lv in levels if lv.distance_pct(spot) <= proximity_pct]
    return sorted(near, key=lambda lv: (lv.distance_pct(spot), -lv.touches))


def option_type_for(level: SpotLevel) -> str:
    """Resistance breaks upward and squeezes call writers; support the mirror."""
    return "CE" if level.kind == "resistance" else "PE"
