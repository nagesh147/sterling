"""Projected daily/weekly ranges via frozen, leakage-free rolling weighted
empirical quantiles (spec §8). STERLING-DESIGNED; target coverage and
lookbacks are CALIBRATION-REQUIRED.

Range endpoints are always frozen from the session/week open — an
invariant, not a toggle. The in-progress (current) period is NEVER included
in the fitting pool, regardless of how much of it has already unfolded by
the time this runs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.navigator.quality import ValidatedCandles, ist_calendar_dates

MODEL_VERSION = "projected_ranges_v1"

RangeContext = Literal[
    "INSIDE_BALANCED", "NEAR_UPPER", "NEAR_LOWER", "BREAK_ABOVE", "BREAK_BELOW",
    "REENTERED_FROM_ABOVE", "REENTERED_FROM_BELOW", "UNAVAILABLE",
]


@dataclass(frozen=True)
class PeriodObservation:
    period_open: float
    period_high: float
    period_low: float
    up_excursion: float
    down_excursion: float


@dataclass(frozen=True)
class ProjectedRange:
    available: bool
    period_open: Optional[float] = None
    upper: Optional[float] = None
    lower: Optional[float] = None
    sample_count: int = 0
    target_coverage: float = 0.0
    conditioned: bool = False
    unavailable_reason: Optional[str] = None


@dataclass(frozen=True)
class RangeEvaluation:
    daily: ProjectedRange
    weekly: ProjectedRange
    daily_context: RangeContext
    weekly_context: RangeContext


# ── grouping ─────────────────────────────────────────────────────────────

def _session_groups(candles: ValidatedCandles) -> list[tuple[int, int]]:
    """Contiguous per-IST-calendar-date (start, end_exclusive) index pairs,
    in chronological order."""
    dates = ist_calendar_dates(candles.timestamp_ms)
    groups: list[tuple[int, int]] = []
    start = 0
    for i in range(1, len(dates) + 1):
        if i == len(dates) or dates[i] != dates[start]:
            groups.append((start, i))
            start = i
    return groups


def _week_key(d) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso[0], iso[1])  # (ISO year, ISO week)


def _weekly_groups(candles: ValidatedCandles, session_groups: list[tuple[int, int]]) -> list[tuple[int, int]]:
    dates = ist_calendar_dates(candles.timestamp_ms)
    groups: list[tuple[int, int]] = []
    start = session_groups[0][0]
    current_week = _week_key(dates[start])
    for (s, e) in session_groups:
        wk = _week_key(dates[s])
        if wk != current_week:
            groups.append((start, s))
            start = s
            current_week = wk
    groups.append((start, session_groups[-1][1]))
    return groups


def _period_observations(candles: ValidatedCandles, groups: list[tuple[int, int]]) -> list[PeriodObservation]:
    obs = []
    for (s, e) in groups:
        period_open = float(candles.open[s])
        period_high = float(candles.high[s:e].max())
        period_low = float(candles.low[s:e].min())
        up = max(0.0, (period_high - period_open) / period_open)
        down = max(0.0, (period_open - period_low) / period_open)
        obs.append(PeriodObservation(period_open, period_high, period_low, up, down))
    return obs


# ── weighted empirical quantile ──────────────────────────────────────────

def _decay_weights(n: int, decay: float) -> NDArray[np.float64]:
    """Most recent observation (last in array order) gets weight 1.0; each
    one further back is discounted by one more factor of `decay`."""
    ages = np.arange(n - 1, -1, -1)
    return decay ** ages


def _weighted_quantile(values: NDArray[np.float64], weights: NDArray[np.float64], q: float) -> float:
    order = np.argsort(values)
    v = values[order]
    w = weights[order]
    cum = np.cumsum(w)
    total = cum[-1]
    if total <= 0:
        return float(v[-1])
    threshold = q * total
    idx = int(np.searchsorted(cum, threshold))
    idx = min(idx, len(v) - 1)
    return float(v[idx])


def _bucket_condition(obs: list[PeriodObservation], config) -> tuple[list[int], Optional[str]]:
    """Buckets the completed observations by realized-range tercile
    (STERLING-DESIGNED conditioning proxy, computed only from information
    already available at the open) and returns the bucket matching the
    most recently completed observation's own range, provided that bucket
    has enough samples; otherwise falls back to the full unconditional
    pool and is labeled as such."""
    if not config.condition_on_volatility or len(obs) < config.min_condition_bucket * 2:
        return list(range(len(obs))), None
    ranges = np.array([o.up_excursion + o.down_excursion for o in obs])
    low_cut, high_cut = np.percentile(ranges, [33.3, 66.7])

    def _bucket_of(v: float) -> str:
        if v <= low_cut:
            return "low"
        if v >= high_cut:
            return "high"
        return "mid"

    labels = [_bucket_of(r) for r in ranges]
    current_label = labels[-1]
    idxs = [i for i, lb in enumerate(labels) if lb == current_label]
    if len(idxs) < config.min_condition_bucket:
        return list(range(len(obs))), None
    return idxs, current_label


def _freeze(obs: list[PeriodObservation], config, current_open: float) -> ProjectedRange:
    idxs, bucket_label = _bucket_condition(obs, config)
    used = [obs[i] for i in idxs]
    ups = np.array([o.up_excursion for o in used])
    downs = np.array([o.down_excursion for o in used])
    weights = _decay_weights(len(used), config.decay)
    q_up = _weighted_quantile(ups, weights, config.target_coverage)
    q_down = _weighted_quantile(downs, weights, config.target_coverage)
    return ProjectedRange(
        available=True,
        period_open=current_open,
        upper=current_open * (1.0 + q_up),
        lower=current_open * (1.0 - q_down),
        sample_count=len(used),
        target_coverage=config.target_coverage,
        conditioned=bucket_label is not None,
    )


def _compute_one(
    candles: ValidatedCandles, groups: list[tuple[int, int]], *, lookback: int, min_periods: int, config,
) -> ProjectedRange:
    if len(groups) < 2:
        return ProjectedRange(available=False, unavailable_reason="not enough periods observed yet")

    current_start, current_end = groups[-1]
    completed_groups = groups[:-1][-lookback:]
    completed_obs = _period_observations(candles, completed_groups)
    if len(completed_obs) < min_periods:
        return ProjectedRange(
            available=False,
            unavailable_reason=f"only {len(completed_obs)} completed periods, need {min_periods}",
        )
    current_open = float(candles.open[current_start])
    return _freeze(completed_obs, config, current_open)


def classify_range_context(
    *,
    range_result: ProjectedRange,
    period_high: float,
    period_low: float,
    close: float,
    edge_tolerance_atr: float,
    atr_value: Optional[float],
) -> RangeContext:
    if not range_result.available:
        return "UNAVAILABLE"
    upper, lower = range_result.upper, range_result.lower
    if atr_value is not None and atr_value > 0:
        tol = edge_tolerance_atr * atr_value
    else:
        # No ATR supplied — fall back to a band-relative proxy tolerance.
        tol = edge_tolerance_atr * (upper - lower) * 0.1

    broke_above = period_high > upper
    broke_below = period_low < lower
    if broke_above and close <= upper:
        return "REENTERED_FROM_ABOVE"
    if broke_below and close >= lower:
        return "REENTERED_FROM_BELOW"
    if close > upper:
        return "BREAK_ABOVE"
    if close < lower:
        return "BREAK_BELOW"
    if close >= upper - tol:
        return "NEAR_UPPER"
    if close <= lower + tol:
        return "NEAR_LOWER"
    return "INSIDE_BALANCED"


def evaluate_ranges(candles: ValidatedCandles, config, *, atr_value: Optional[float] = None) -> RangeEvaluation:
    session_groups = _session_groups(candles)
    weekly_groups = _weekly_groups(candles, session_groups)

    daily = _compute_one(
        candles, session_groups, lookback=config.daily_lookback_sessions,
        min_periods=config.daily_min_sessions, config=config,
    )
    weekly = _compute_one(
        candles, weekly_groups, lookback=config.weekly_lookback_periods,
        min_periods=config.weekly_min_periods, config=config,
    )

    ds, de = session_groups[-1]
    daily_context = classify_range_context(
        range_result=daily,
        period_high=float(candles.high[ds:de].max()), period_low=float(candles.low[ds:de].min()),
        close=float(candles.close[-1]), edge_tolerance_atr=config.edge_tolerance_atr, atr_value=atr_value,
    )
    ws, we = weekly_groups[-1]
    weekly_context = classify_range_context(
        range_result=weekly,
        period_high=float(candles.high[ws:we].max()), period_low=float(candles.low[ws:we].min()),
        close=float(candles.close[-1]), edge_tolerance_atr=config.edge_tolerance_atr, atr_value=atr_value,
    )

    return RangeEvaluation(daily=daily, weekly=weekly, daily_context=daily_context, weekly_context=weekly_context)
