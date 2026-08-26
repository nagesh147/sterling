"""Anchored VWAP structure, pullback/continuation signal families, grading,
and stop/target proposal (spec §7). STERLING-DESIGNED — the supplied source
material describes behavior, not these formulas.

This module only ever knows about price/volume. Whether a continuation
signal is promoted to `IMPULSE_CONTINUATION` requires the volatility regime
and a frozen range edge from other components, so that promotion decision
lives in `fusion.py`, not here (spec §4.1 bounded contexts).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.indicators.atr import compute_atr
from app.engines.navigator.quality import ValidatedCandles, ist_calendar_dates

MODEL_VERSION = "avwap_v1"
EPSILON = 1e-9

AvwapFamily = Literal[
    "PULLBACK_LONG", "PULLBACK_SHORT", "CONTINUATION_LONG", "CONTINUATION_SHORT",
]
AvwapGradeLabel = Literal["A+", "A", "B", "none"]


# ─────────────────────────────────────────────────────────────────────────
# Confirmed swing pivots (spec §7.1) — no backfill, deterministic tie-break
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ConfirmedPivot:
    bar_index: int
    visible_from_index: int  # bar_index + right_bars — first index the anchor may be used at
    price: float


def _raw_extrema_indices(values: NDArray[np.float64], left: int, right: int, kind: str) -> list[int]:
    """Per-bar pivot condition exactly as specified: strictly greater/less
    than the left window, greater-or-equal/less-or-equal to the right
    window. Left in front of a plateau of ties, later members of that same
    plateau structurally fail the strict side (see `_confirmed_pivots`)."""
    n = len(values)
    out: list[int] = []
    for i in range(left, n - right):
        left_win = values[i - left:i]
        right_win = values[i + 1:i + right + 1]
        if kind == "high":
            if values[i] > left_win.max() and values[i] >= right_win.max():
                out.append(i)
        else:
            if values[i] < left_win.min() and values[i] <= right_win.min():
                out.append(i)
    return out


def _confirmed_pivots(values: NDArray[np.float64], left: int, right: int, kind: str) -> list[ConfirmedPivot]:
    """Deterministic tie-break: the strict-left/`>=`-right formula on its
    own always resolves a plateau of exactly-tied bars to its FIRST member
    (later members fail the strict-left check against an equal predecessor
    within their own left window). To honor "for equal extrema, keep the
    most recent candidate", each raw candidate is re-anchored to the most
    recent bar within its own right window that exactly ties its value —
    that bar becomes the actual anchor origin, and its confirmation waits
    for `right` bars past THAT bar to close."""
    n = len(values)
    raw = _raw_extrema_indices(values, left, right, kind)
    pivots: list[ConfirmedPivot] = []
    for i in raw:
        j = i
        for k in range(i + 1, min(i + right, n - 1) + 1):
            if values[k] == values[i]:
                j = k
        if j + right >= n:
            j = i  # not enough bars yet to confirm the re-anchored candidate
        pivots.append(ConfirmedPivot(bar_index=j, visible_from_index=j + right, price=float(values[j])))
    return pivots


# ─────────────────────────────────────────────────────────────────────────
# Anchored VWAP + session VWAP
# ─────────────────────────────────────────────────────────────────────────

def _piecewise_avwap(typical: NDArray[np.float64], volume: NDArray[np.float64], anchor_idx: NDArray[np.int64]) -> NDArray[np.float64]:
    """AVWAP(active_anchor(t), t) where the active anchor can change over
    time as new pivots are confirmed. `anchor_idx[t] == -1` means no anchor
    yet (caller must treat that bar as warming up).

    The sum always starts at the anchor bar itself (`a`), even though the
    anchor only becomes usable starting at `visible_from = a + right_bars`
    — "the AVWAP may include volume from the origin" (spec §7.1). Prefix
    sums make this an O(1)-per-bar lookup regardless of how far back the
    active anchor sits, and naturally handle the anchor changing over time
    since each `t` looks its own anchor up independently.

    Falls back to an unweighted mean of typical price over [a, t] whenever
    that window's cumulative volume is zero — NSE/BSE INDEX candles (NIFTY
    50, NIFTY BANK, SENSEX, ...) always report volume=0 since an index has
    no traded volume of its own, so a strictly volume-weighted average
    would stay NaN forever on every index underlying regardless of anchor
    or how much history is fetched, permanently stuck "warming up"."""
    prefix_num = np.concatenate(([0.0], np.cumsum(typical * volume)))
    prefix_den = np.concatenate(([0.0], np.cumsum(volume)))
    prefix_typical = np.concatenate(([0.0], np.cumsum(typical)))
    n = len(typical)
    out = np.full(n, np.nan)
    for t in range(n):
        a = int(anchor_idx[t])
        if a < 0:
            continue
        den = prefix_den[t + 1] - prefix_den[a]
        if den > 0:
            out[t] = (prefix_num[t + 1] - prefix_num[a]) / den
        else:
            out[t] = (prefix_typical[t + 1] - prefix_typical[a]) / (t + 1 - a)
    return out


def _session_vwap(candles: ValidatedCandles) -> NDArray[np.float64]:
    """Resets at the official exchange session open in Asia/Kolkata, not
    UTC midnight. No holiday calendar is needed here: the input candle
    series only ever contains bars for sessions the exchange actually
    traded, so a change in IST calendar date between consecutive bars is
    exactly a new session boundary."""
    typical = candles.typical_price()
    volume = candles.volume
    dates = ist_calendar_dates(candles.timestamp_ms)
    n = candles.n
    out = np.full(n, np.nan)
    cum_num = 0.0
    cum_den = 0.0
    prev_date = None
    for i in range(n):
        if dates[i] != prev_date:
            cum_num = 0.0
            cum_den = 0.0
            prev_date = dates[i]
        cum_num += typical[i] * volume[i]
        cum_den += volume[i]
        out[i] = cum_num / cum_den if cum_den > 0 else np.nan
    return out


def _normalized_slope(x: NDArray[np.float64], k: int, atr_arr: NDArray[np.float64]) -> NDArray[np.float64]:
    """slope_x(t) = (x[t] - x[t-k]) / max(ATR[t], epsilon) / k — comparable
    across instruments regardless of price scale."""
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(k, n):
        if np.isnan(x[t]) or np.isnan(x[t - k]) or np.isnan(atr_arr[t]):
            continue
        denom = atr_arr[t] if atr_arr[t] > EPSILON else EPSILON
        out[t] = (x[t] - x[t - k]) / denom / k
    return out


def _relative_volume(volume: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """Current bar's volume vs. the mean of the PRIOR `period` bars
    (excluding the current bar, to avoid a bar inflating its own baseline)."""
    n = len(volume)
    out = np.full(n, np.nan)
    for t in range(period, n):
        window = volume[t - period:t]
        avg = window.mean()
        out[t] = volume[t] / avg if avg > 0 else np.nan
    return out


@dataclass(frozen=True)
class AvwapStructure:
    upper: NDArray[np.float64]
    mid: NDArray[np.float64]
    lower: NDArray[np.float64]
    session_vwap: NDArray[np.float64]
    mid_slope: NDArray[np.float64]
    upper_slope: NDArray[np.float64]
    lower_slope: NDArray[np.float64]
    warming_up: NDArray[np.bool_]
    high_anchor_idx: NDArray[np.int64]
    low_anchor_idx: NDArray[np.int64]
    atr: NDArray[np.float64]
    relative_volume: NDArray[np.float64]
    high_pivots: list
    low_pivots: list


def compute_structure(candles: ValidatedCandles, config) -> AvwapStructure:
    n = candles.n
    typical = candles.typical_price()
    volume = candles.volume

    high_pivots = _confirmed_pivots(candles.high, config.pivot_left_bars, config.pivot_right_bars, "high")
    low_pivots = _confirmed_pivots(candles.low, config.pivot_left_bars, config.pivot_right_bars, "low")

    high_anchor_idx = np.full(n, -1, dtype=np.int64)
    low_anchor_idx = np.full(n, -1, dtype=np.int64)
    for p in high_pivots:
        if p.visible_from_index < n:
            high_anchor_idx[p.visible_from_index:] = p.bar_index
    for p in low_pivots:
        if p.visible_from_index < n:
            low_anchor_idx[p.visible_from_index:] = p.bar_index

    high_anchor_vwap = _piecewise_avwap(typical, volume, high_anchor_idx)
    low_anchor_vwap = _piecewise_avwap(typical, volume, low_anchor_idx)

    warming_up = (high_anchor_idx < 0) | (low_anchor_idx < 0) | np.isnan(high_anchor_vwap) | np.isnan(low_anchor_vwap)

    upper = np.where(warming_up, np.nan, np.maximum(high_anchor_vwap, low_anchor_vwap))
    lower = np.where(warming_up, np.nan, np.minimum(high_anchor_vwap, low_anchor_vwap))
    mid = np.where(warming_up, np.nan, (upper + lower) / 2.0)

    session_vwap = _session_vwap(candles)
    atr_arr = compute_atr(candles.high, candles.low, candles.close, config.atr_period)
    atr_arr = atr_arr.astype(np.float64).copy()
    atr_arr[: config.atr_period] = np.nan  # compute_atr zero-fills the warmup zone; NaN it out explicitly

    mid_slope = _normalized_slope(mid, config.slope_lookback_bars, atr_arr)
    upper_slope = _normalized_slope(upper, config.slope_lookback_bars, atr_arr)
    lower_slope = _normalized_slope(lower, config.slope_lookback_bars, atr_arr)

    relative_volume = _relative_volume(volume, config.relative_volume_period)

    return AvwapStructure(
        upper=upper, mid=mid, lower=lower, session_vwap=session_vwap,
        mid_slope=mid_slope, upper_slope=upper_slope, lower_slope=lower_slope,
        warming_up=warming_up, high_anchor_idx=high_anchor_idx, low_anchor_idx=low_anchor_idx,
        atr=atr_arr, relative_volume=relative_volume,
        high_pivots=high_pivots, low_pivots=low_pivots,
    )


# ─────────────────────────────────────────────────────────────────────────
# Signal families + grade (spec §7.2, §7.3) — STERLING-DESIGNED
# ─────────────────────────────────────────────────────────────────────────

def _bullish_structure(t: int, structure: AvwapStructure, candles: ValidatedCandles, config) -> bool:
    if structure.warming_up[t]:
        return False
    if np.isnan(structure.mid_slope[t]):
        return False
    close_above_mid = candles.close[t] > structure.mid[t]
    slope_ok = structure.mid_slope[t] > config.min_slope_atr_per_bar
    not_strongly_negative = (
        (np.isnan(structure.upper_slope[t]) or structure.upper_slope[t] >= -config.min_slope_atr_per_bar)
        and (np.isnan(structure.lower_slope[t]) or structure.lower_slope[t] >= -config.min_slope_atr_per_bar)
    )
    return bool(close_above_mid and slope_ok and not_strongly_negative)


def _bearish_structure(t: int, structure: AvwapStructure, candles: ValidatedCandles, config) -> bool:
    if structure.warming_up[t]:
        return False
    if np.isnan(structure.mid_slope[t]):
        return False
    close_below_mid = candles.close[t] < structure.mid[t]
    slope_ok = structure.mid_slope[t] < -config.min_slope_atr_per_bar
    not_strongly_positive = (
        (np.isnan(structure.upper_slope[t]) or structure.upper_slope[t] <= config.min_slope_atr_per_bar)
        and (np.isnan(structure.lower_slope[t]) or structure.lower_slope[t] <= config.min_slope_atr_per_bar)
    )
    return bool(close_below_mid and slope_ok and not_strongly_positive)


def _touched_level(low_or_high: float, levels: tuple, atr_val: float, tolerance_atr: float) -> bool:
    if atr_val <= 0 or np.isnan(atr_val):
        return False
    tol = tolerance_atr * atr_val
    return any(abs(low_or_high - lvl) <= tol for lvl in levels if not np.isnan(lvl))


def _distance_from_mid_atr(price: float, mid: float, atr_val: float) -> float:
    if atr_val <= 0 or np.isnan(atr_val) or np.isnan(mid):
        return float("inf")
    return abs(price - mid) / atr_val


def _pullback_long_raw(t: int, structure: AvwapStructure, candles: ValidatedCandles, config) -> bool:
    if not _bullish_structure(t, structure, candles, config):
        return False
    levels = (structure.lower[t], structure.upper[t], structure.mid[t])
    if not _touched_level(candles.low[t], levels, structure.atr[t], config.touch_tolerance_atr):
        return False
    if not (candles.close[t] > min(v for v in levels if not np.isnan(v))):
        return False
    body_ok = candles.close[t] >= candles.open[t]
    lower_wick = min(candles.open[t], candles.close[t]) - candles.low[t]
    wick_rejection_ok = structure.atr[t] > 0 and lower_wick / structure.atr[t] >= config.min_body_atr
    if not (body_ok or wick_rejection_ok):
        return False
    if _distance_from_mid_atr(candles.close[t], structure.mid[t], structure.atr[t]) > config.max_extension_atr:
        return False
    return True


def _pullback_short_raw(t: int, structure: AvwapStructure, candles: ValidatedCandles, config) -> bool:
    if not _bearish_structure(t, structure, candles, config):
        return False
    levels = (structure.lower[t], structure.upper[t], structure.mid[t])
    if not _touched_level(candles.high[t], levels, structure.atr[t], config.touch_tolerance_atr):
        return False
    if not (candles.close[t] < max(v for v in levels if not np.isnan(v))):
        return False
    body_ok = candles.close[t] <= candles.open[t]
    upper_wick = candles.high[t] - max(candles.open[t], candles.close[t])
    wick_rejection_ok = structure.atr[t] > 0 and upper_wick / structure.atr[t] >= config.min_body_atr
    if not (body_ok or wick_rejection_ok):
        return False
    if _distance_from_mid_atr(candles.close[t], structure.mid[t], structure.atr[t]) > config.max_extension_atr:
        return False
    return True


def _continuation_long_raw(t: int, structure: AvwapStructure, candles: ValidatedCandles, config) -> bool:
    if t == 0 or not _bullish_structure(t, structure, candles, config):
        return False
    if np.isnan(structure.upper[t]) or np.isnan(structure.upper[t - 1]) or np.isnan(structure.atr[t]):
        return False
    buf = config.breakout_buffer_atr * structure.atr[t]
    if not (candles.close[t - 1] <= structure.upper[t - 1] + buf):
        return False
    if not (candles.close[t] > structure.upper[t] + buf):
        return False
    body = abs(candles.close[t] - candles.open[t])
    if structure.atr[t] <= 0 or body / structure.atr[t] < config.min_body_atr:
        return False
    if np.isnan(structure.relative_volume[t]) or structure.relative_volume[t] < config.min_relative_volume:
        return False
    if _distance_from_mid_atr(candles.close[t], structure.mid[t], structure.atr[t]) > config.max_extension_atr:
        return False
    return True


def _continuation_short_raw(t: int, structure: AvwapStructure, candles: ValidatedCandles, config) -> bool:
    if t == 0 or not _bearish_structure(t, structure, candles, config):
        return False
    if np.isnan(structure.lower[t]) or np.isnan(structure.lower[t - 1]) or np.isnan(structure.atr[t]):
        return False
    buf = config.breakout_buffer_atr * structure.atr[t]
    if not (candles.close[t - 1] >= structure.lower[t - 1] - buf):
        return False
    if not (candles.close[t] < structure.lower[t] - buf):
        return False
    body = abs(candles.close[t] - candles.open[t])
    if structure.atr[t] <= 0 or body / structure.atr[t] < config.min_body_atr:
        return False
    if np.isnan(structure.relative_volume[t]) or structure.relative_volume[t] < config.min_relative_volume:
        return False
    if _distance_from_mid_atr(candles.close[t], structure.mid[t], structure.atr[t]) > config.max_extension_atr:
        return False
    return True


@dataclass(frozen=True)
class FamilyTimeline:
    """Which setup family (if any) held on EVERY bar, plus the cooldown-filtered
    ``fired`` mask.

    ``evaluate_avwap`` only ever decides at the last bar, but it already has to
    walk the whole series for cooldown bookkeeping. The chart overlay needs
    exactly that per-bar answer, so it is computed here once instead of twice:
    an overlay drawn from a second implementation could show the user a setup
    the engine never saw, or hide one it acted on.
    """

    pullback_long: NDArray[np.bool_]
    pullback_short: NDArray[np.bool_]
    continuation_long: NDArray[np.bool_]
    continuation_short: NDArray[np.bool_]
    raw: NDArray[np.bool_]
    fired: NDArray[np.bool_]

    def family_at(self, t: int) -> Optional[tuple[AvwapFamily, int]]:
        """``(family, direction)`` owning bar ``t``, in the engine's precedence
        order, or None when no family held there."""
        if self.pullback_long[t]:
            return "PULLBACK_LONG", 1
        if self.pullback_short[t]:
            return "PULLBACK_SHORT", -1
        if self.continuation_long[t]:
            return "CONTINUATION_LONG", 1
        if self.continuation_short[t]:
            return "CONTINUATION_SHORT", -1
        return None


def family_timeline(candles: ValidatedCandles, structure: AvwapStructure, config) -> FamilyTimeline:
    """Evaluate the four setup families on every bar and apply the cooldown."""
    n = candles.n
    pullback_long = np.array([_pullback_long_raw(i, structure, candles, config) for i in range(n)])
    pullback_short = np.array([_pullback_short_raw(i, structure, candles, config) for i in range(n)])
    continuation_long = np.array([_continuation_long_raw(i, structure, candles, config) for i in range(n)])
    continuation_short = np.array([_continuation_short_raw(i, structure, candles, config) for i in range(n)])
    raw = pullback_long | pullback_short | continuation_long | continuation_short
    return FamilyTimeline(
        pullback_long=pullback_long, pullback_short=pullback_short,
        continuation_long=continuation_long, continuation_short=continuation_short,
        raw=raw, fired=_apply_cooldown(raw, config.cooldown_bars),
    )


def _apply_cooldown(raw_mask: NDArray[np.bool_], cooldown_bars: int) -> NDArray[np.bool_]:
    n = len(raw_mask)
    out = np.zeros(n, dtype=bool)
    last_fire = -(10 ** 9)
    for t in range(n):
        if raw_mask[t] and (t - last_fire) > cooldown_bars:
            out[t] = True
            last_fire = t
    return out


@dataclass(frozen=True)
class AvwapGradeResult:
    grade: AvwapGradeLabel
    score: float
    components: dict


def _grade_pullback(t: int, structure: AvwapStructure, candles: ValidatedCandles, config, direction: str, range_supports: Optional[bool]) -> AvwapGradeResult:
    atr_val = structure.atr[t] if structure.atr[t] > 0 else EPSILON
    mid_slope = abs(structure.mid_slope[t]) if not np.isnan(structure.mid_slope[t]) else 0.0

    structure_pts = min(25.0, 12.5 * (1 if True else 0) + 12.5 * min(1.0, mid_slope / max(config.min_slope_atr_per_bar, EPSILON)))
    levels = [v for v in (structure.lower[t], structure.upper[t], structure.mid[t]) if not np.isnan(v)]
    if direction == "long":
        touch_dist = min(abs(candles.low[t] - lvl) for lvl in levels) / atr_val
        rejection_strength = (candles.close[t] - candles.low[t]) / atr_val
    else:
        touch_dist = min(abs(candles.high[t] - lvl) for lvl in levels) / atr_val
        rejection_strength = (candles.high[t] - candles.close[t]) / atr_val
    trigger_pts = min(20.0, 20.0 * max(0.0, 1.0 - touch_dist / max(config.touch_tolerance_atr, EPSILON)) * min(1.0, rejection_strength / max(config.min_body_atr, EPSILON) + 0.5))

    rel_vol = structure.relative_volume[t]
    participation_pts = 0.0 if np.isnan(rel_vol) else min(15.0, 15.0 * min(1.0, rel_vol / max(config.min_relative_volume, EPSILON)))

    body = abs(candles.close[t] - candles.open[t])
    body_atr = body / atr_val
    candle_pts = min(15.0, 15.0 * min(1.0, body_atr / max(config.min_body_atr, EPSILON)))

    ext = _distance_from_mid_atr(candles.close[t], structure.mid[t], structure.atr[t])
    extension_pts = max(0.0, 15.0 * (1.0 - min(1.0, ext / max(config.max_extension_atr, EPSILON))))

    range_pts = 10.0 if range_supports else (5.0 if range_supports is None else 0.0)

    total = structure_pts + trigger_pts + participation_pts + candle_pts + extension_pts + range_pts
    grade = _grade_label(total, config)
    return AvwapGradeResult(
        grade=grade, score=total,
        components=dict(structure=structure_pts, trigger=trigger_pts, participation=participation_pts,
                         candle_quality=candle_pts, extension=extension_pts, range_context=range_pts),
    )


def _grade_continuation(t: int, structure: AvwapStructure, candles: ValidatedCandles, config, direction: str, range_supports: Optional[bool]) -> AvwapGradeResult:
    atr_val = structure.atr[t] if structure.atr[t] > 0 else EPSILON
    mid_slope = abs(structure.mid_slope[t]) if not np.isnan(structure.mid_slope[t]) else 0.0
    structure_pts = min(25.0, 12.5 + 12.5 * min(1.0, mid_slope / max(config.min_slope_atr_per_bar, EPSILON)))

    level = structure.upper[t] if direction == "long" else structure.lower[t]
    buf = config.breakout_buffer_atr * atr_val
    breakout_extent = abs(candles.close[t] - level) / max(buf, EPSILON)
    trigger_pts = min(20.0, 20.0 * min(1.0, breakout_extent / 2.0))

    rel_vol = structure.relative_volume[t]
    participation_pts = 0.0 if np.isnan(rel_vol) else min(15.0, 15.0 * min(1.0, rel_vol / max(config.min_relative_volume, EPSILON)))

    body = abs(candles.close[t] - candles.open[t])
    body_atr = body / atr_val
    candle_pts = min(15.0, 15.0 * min(1.0, body_atr / max(config.min_body_atr, EPSILON)))

    ext = _distance_from_mid_atr(candles.close[t], structure.mid[t], structure.atr[t])
    extension_pts = max(0.0, 15.0 * (1.0 - min(1.0, ext / max(config.max_extension_atr, EPSILON))))

    range_pts = 10.0 if range_supports else (5.0 if range_supports is None else 0.0)

    total = structure_pts + trigger_pts + participation_pts + candle_pts + extension_pts + range_pts
    grade = _grade_label(total, config)
    return AvwapGradeResult(
        grade=grade, score=total,
        components=dict(structure=structure_pts, trigger=trigger_pts, participation=participation_pts,
                         candle_quality=candle_pts, extension=extension_pts, range_context=range_pts),
    )


def _grade_label(score: float, config) -> AvwapGradeLabel:
    if score >= config.grade_a_plus_min:
        return "A+"
    if score >= config.grade_a_min:
        return "A"
    if score >= config.grade_b_min:
        return "B"
    return "none"


# ─────────────────────────────────────────────────────────────────────────
# Stop / target proposal (spec §7.4)
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StopTargetProposal:
    accepted: bool
    stop: Optional[float] = None
    target: Optional[float] = None
    risk_points: Optional[float] = None
    reject_reason: Optional[str] = None
    nearest_range_edge: Optional[float] = None


def propose_stop_target(
    *,
    direction: Literal["long", "short"],
    entry_reference: float,
    trigger_bar_low: float,
    trigger_bar_high: float,
    upper: float,
    lower: float,
    atr: float,
    tick_size: float,
    config,
    nearest_range_edge: Optional[float] = None,
) -> StopTargetProposal:
    if atr <= 0 or np.isnan(atr):
        return StopTargetProposal(accepted=False, reject_reason="ATR unavailable")

    if direction == "long":
        stop = min(trigger_bar_low, lower) - atr * config.stop_buffer_atr
        if stop >= entry_reference:
            return StopTargetProposal(accepted=False, reject_reason="stop is on the wrong side of entry")
        risk_points = entry_reference - stop
    else:
        stop = max(trigger_bar_high, upper) + atr * config.stop_buffer_atr
        if stop <= entry_reference:
            return StopTargetProposal(accepted=False, reject_reason="stop is on the wrong side of entry")
        risk_points = stop - entry_reference

    if risk_points <= tick_size:
        return StopTargetProposal(accepted=False, reject_reason="risk_points <= tick_size", risk_points=risk_points)
    if risk_points / atr > config.max_stop_distance_atr:
        return StopTargetProposal(accepted=False, reject_reason="risk_points/ATR exceeds max_stop_distance_atr", risk_points=risk_points)

    if direction == "long":
        target = entry_reference + config.target_r * risk_points
        if nearest_range_edge is not None and nearest_range_edge < target:
            return StopTargetProposal(
                accepted=False, reject_reason="nearest range edge sits inside the target R-multiple",
                risk_points=risk_points, nearest_range_edge=nearest_range_edge,
            )
    else:
        target = entry_reference - config.target_r * risk_points
        if nearest_range_edge is not None and nearest_range_edge > target:
            return StopTargetProposal(
                accepted=False, reject_reason="nearest range edge sits inside the target R-multiple",
                risk_points=risk_points, nearest_range_edge=nearest_range_edge,
            )

    stop_rounded = round(round(stop / tick_size) * tick_size, 2)
    target_rounded = round(round(target / tick_size) * tick_size, 2)
    risk_points_rounded = round(round(abs(entry_reference - stop_rounded) / tick_size) * tick_size, 2)

    return StopTargetProposal(
        accepted=True, stop=stop_rounded, target=target_rounded, risk_points=risk_points_rounded,
        nearest_range_edge=nearest_range_edge,
    )


# ─────────────────────────────────────────────────────────────────────────
# Top-level evaluation at the latest bar
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AvwapEvaluation:
    family: Optional[AvwapFamily]
    direction: Literal[-1, 0, 1]
    grade: AvwapGradeResult
    stop_target: Optional[StopTargetProposal]
    warming_up: bool


def evaluate_avwap(
    candles: ValidatedCandles, config, *, range_supports: Optional[bool] = None, tick_size: float = 0.05,
) -> tuple[AvwapStructure, AvwapEvaluation]:
    """Evaluate signal families across the whole series (needed for cooldown
    bookkeeping) and report the result AT THE LAST BAR — the only bar
    Navigator ever acts on."""
    structure = compute_structure(candles, config)
    n = candles.n
    t = n - 1

    if structure.warming_up[t]:
        grade = AvwapGradeResult(grade="none", score=0.0, components={})
        return structure, AvwapEvaluation(family=None, direction=0, grade=grade, stop_target=None, warming_up=True)

    timeline = family_timeline(candles, structure, config)
    picked = timeline.family_at(t) if timeline.fired[t] else None

    if picked is None:
        grade = AvwapGradeResult(grade="none", score=0.0, components={})
        return structure, AvwapEvaluation(family=None, direction=0, grade=grade, stop_target=None, warming_up=False)

    family, direction = picked
    side: Literal["long", "short"] = "long" if direction == 1 else "short"
    if family in ("PULLBACK_LONG", "PULLBACK_SHORT"):
        grade = _grade_pullback(t, structure, candles, config, side, range_supports)
    else:
        grade = _grade_continuation(t, structure, candles, config, side, range_supports)

    if grade.grade == "none":
        return structure, AvwapEvaluation(family=None, direction=0, grade=grade, stop_target=None, warming_up=False)

    proposal = propose_stop_target(
        direction="long" if direction == 1 else "short",
        entry_reference=float(candles.close[t]),
        trigger_bar_low=float(candles.low[t]),
        trigger_bar_high=float(candles.high[t]),
        upper=float(structure.upper[t]), lower=float(structure.lower[t]),
        atr=float(structure.atr[t]), tick_size=tick_size, config=config,
    )

    return structure, AvwapEvaluation(family=family, direction=direction, grade=grade, stop_target=proposal, warming_up=False)
