"""
Sterling v4 — Signal feature blocks.

Pure numpy-based feature extractors used by both `signal_engine.compute_signal`
(per-bar live path) and `mtf_vectorizer.build_signals_full` (vectorised
backtest). Each function consumes raw OHLCV arrays plus the precomputed
indicator series the caller is expected to share, and returns flags + values.

No I/O, no Candle, no time.time(). Behaviour is parametrised by
`SignalThresholds` so callers can override defaults for boundary tests.

Why per-bar callers don't just call the vectorised path: the live engine
operates on a rolling window where only the latest bar's flags matter, and
the function must be cheap to call from a hot endpoint. The vectorised path
is O(N) — building it for one bar would dominate latency.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from app.engines.directional.signal_weights import SignalThresholds
from app.engines.directional.signal_coherence import compute_coherence, coherence_penalty


# ── Constants for adaptive feature lookback windows ──────────────────────
_RSI_EXTREME_LOOKBACK: int = 100
_VOL_ZSCORE_LOOKBACK:  int = 40


# ── Per-bar feature dataclasses ──────────────────────────────────────────

@dataclass(frozen=True)
class FlipState:
    """Supertrend-flip and trend state at the latest bar."""
    trend: int                  # 1 / -1 / 0
    all_green: bool
    all_red: bool
    green_arrow: bool
    red_arrow: bool
    st_trends: Tuple[int, int, int]
    st_values: Tuple[float, float, float]


@dataclass(frozen=True)
class RsiState:
    """RSI gate + momentum-bonus state."""
    rsi: float
    rsi_ok: bool
    rsi_momentum: bool


@dataclass(frozen=True)
class SqueezeState:
    """Bollinger-inside-Keltner squeeze + breakout state at the latest bar."""
    squeezed: bool
    breakout_long: bool
    breakout_short: bool
    squeeze_ok: bool


@dataclass(frozen=True)
class HaState:
    """Heikin-Ashi alignment + HA/real divergence state."""
    ha_aligned: bool
    ha_real_aligned: bool
    ha_real_div_pct: float
    ha_close: float


@dataclass(frozen=True)
class VolumeState:
    """Volume-spike state at the latest bar."""
    vol_spike: bool
    vol_median: float


@dataclass(frozen=True)
class CvdState:
    """Cumulative-volume-delta divergence state."""
    cvd_sum: float
    cvd_abs_sum: float
    cvd_divergent: bool


@dataclass(frozen=True)
class MtfBoostState:
    """Multi-timeframe alignment between signal-TF trend and macro regime."""
    aligned: bool


# ── Per-bar building blocks ──────────────────────────────────────────────

def flip_state_at(
    st_trends_now: Tuple[int, int, int],
    st_trends_prev: Tuple[int, int, int],
    st_values_now: Tuple[float, float, float],
    st_threshold: int = 3,
) -> FlipState:
    """
    Compute trend, alignment, and fresh-arrow flags from the three Supertrend
    trend values at the latest and previous bars.

    `st_threshold` is the count of agreeing STs required to declare a side
    fully aligned. Default 3 is unanimous; 2 enables partial-alignment regimes.
    """
    green_count = sum(1 for t in st_trends_now if t == 1)
    red_count   = sum(1 for t in st_trends_now if t == -1)
    prev_green  = sum(1 for t in st_trends_prev if t == 1)
    prev_red    = sum(1 for t in st_trends_prev if t == -1)

    all_green_now  = green_count >= st_threshold
    all_red_now    = red_count   >= st_threshold
    all_green_prev = prev_green  >= st_threshold
    all_red_prev   = prev_red    >= st_threshold

    green_arrow = all_green_now and not all_green_prev
    red_arrow   = all_red_now   and not all_red_prev

    if all_green_now:
        trend = 1
    elif all_red_now:
        trend = -1
    else:
        trend = 0

    return FlipState(
        trend=trend,
        all_green=all_green_now,
        all_red=all_red_now,
        green_arrow=green_arrow,
        red_arrow=red_arrow,
        st_trends=st_trends_now,
        st_values=st_values_now,
    )


def rsi_state_at(
    rsi_value: float,
    trend: int,
    thresholds: SignalThresholds,
) -> RsiState:
    """
    Evaluate the RSI gate and momentum bonus at the latest bar.

    `rsi_ok` is the base "RSI in entry band" gate; `rsi_momentum` is the
    optional bonus when RSI is in the stronger momentum-confirming sub-band.
    Both are False when `trend == 0`.
    """
    t = thresholds
    if trend == 1:
        ok  = t.rsi_long_lo  < rsi_value < t.rsi_long_hi
        mom = t.rsi_long_mom_lo < rsi_value < t.rsi_long_mom_hi
    elif trend == -1:
        ok  = t.rsi_short_lo < rsi_value < t.rsi_short_hi
        mom = t.rsi_short_mom_lo < rsi_value < t.rsi_short_mom_hi
    else:
        ok = False
        mom = False
    return RsiState(rsi=float(rsi_value), rsi_ok=bool(ok), rsi_momentum=bool(mom))


def squeeze_state_at(
    close_now:    float,
    bb_lo_prev:   float,
    bb_hi_prev:   float,
    kc_lo_prev:   float,
    kc_hi_prev:   float,
    bb_lo_now:    float,
    bb_hi_now:    float,
) -> SqueezeState:
    """
    Evaluate BB-inside-KC at the previous bar (so the entry bar is the
    breakout bar) and whether the latest close has cleared a Bollinger band.

    Returns the conjunction `squeezed AND (breakout_long OR breakout_short)`
    as `squeeze_ok` — this is the scoring-flag value.
    """
    squeezed       = bool(bb_lo_prev > kc_lo_prev and bb_hi_prev < kc_hi_prev)
    breakout_long  = bool(close_now > bb_hi_now)
    breakout_short = bool(close_now < bb_lo_now)
    return SqueezeState(
        squeezed=squeezed,
        breakout_long=breakout_long,
        breakout_short=breakout_short,
        squeeze_ok=squeezed and (breakout_long or breakout_short),
    )


def ha_state_at(
    ha_bull_now:  bool,
    ha_close_now: float,
    real_close_now: float,
    trend: int,
    thresholds: SignalThresholds,
) -> HaState:
    """
    Evaluate HA body alignment with `trend` and the HA/real divergence flag.

    `ha_real_aligned` fires when |real_close − ha_close| / real_close is
    below the divergence threshold, i.e. HA is still tracking reality and
    hasn't smoothed away an early-warning move.
    """
    if trend == 1:
        aligned = bool(ha_bull_now)
    elif trend == -1:
        aligned = not bool(ha_bull_now)
    else:
        aligned = False
    if real_close_now > 0:
        div_pct = abs(real_close_now - ha_close_now) / real_close_now * 100.0
    else:
        div_pct = 0.0
    return HaState(
        ha_aligned=aligned,
        ha_real_aligned=bool(div_pct < thresholds.ha_real_div_pct_max),
        ha_real_div_pct=float(div_pct),
        ha_close=float(ha_close_now),
    )


def volume_state_at(
    volume_now:    float,
    volume_window: np.ndarray,
    thresholds:    SignalThresholds,
) -> VolumeState:
    """
    Evaluate volume-spike using z-score against the trailing window.
    Falls back to the legacy median-multiplier method when the window is
    too small for a meaningful z-score (< 8 bars or zero std).

    Z-score detects volume climax more consistently across different
    volatility regimes than fixed-mult × median does.
    """
    if volume_window.size == 0:
        return VolumeState(vol_spike=False, vol_median=0.0)
    med = float(np.median(volume_window))
    z_spike = False
    if volume_window.size >= 8:
        mean = float(np.mean(volume_window))
        std = float(np.std(volume_window, ddof=1))
        if std > 0 and mean > 0:
            z = (volume_now - mean) / std
            z_spike = z > thresholds.vol_zscore_threshold
    spike = z_spike or (bool(volume_now > thresholds.vol_spike_mult * med) if med > 0 else False)
    return VolumeState(vol_spike=spike, vol_median=med)


def cvd_state_at(
    open_:  np.ndarray,
    high:   np.ndarray,
    low:    np.ndarray,
    close:  np.ndarray,
    volume: np.ndarray,
    trend:  int,
    thresholds: SignalThresholds,
) -> CvdState:
    """
    Compute the rolling CVD-proxy at the latest bar and flag a divergence
    against `trend`.

    No tick footprint exists in our data, so per-bar delta is the
    position-weighted volume proxy:
        delta = volume * ((close − open) / (high − low))
    summed over `cvd_window` bars. Heavy opposition is when
        |cvd_sum| / sum(|delta|) > cvd_divergence_ratio AND sign opposite trend.
    """
    n = close.shape[0]
    if n == 0:
        return CvdState(cvd_sum=0.0, cvd_abs_sum=0.0, cvd_divergent=False)
    take = min(thresholds.cvd_window, n)
    o = open_[-take:]; h = high[-take:]; l = low[-take:]
    c = close[-take:]; v = volume[-take:]
    tr = h - l
    safe_tr = np.where(tr > 0, tr, np.nan)
    pos = (c - o) / safe_tr
    pos = np.nan_to_num(pos, nan=0.0)
    pos = np.clip(pos, -1.0, 1.0)
    delta = v * pos
    cvd_sum     = float(np.sum(delta))
    cvd_abs_sum = float(np.sum(np.abs(delta)))
    divergent = False
    if trend != 0 and cvd_abs_sum > 0:
        ratio = abs(cvd_sum) / cvd_abs_sum
        if ratio > thresholds.cvd_divergence_ratio:
            if (trend == 1 and cvd_sum < 0) or (trend == -1 and cvd_sum > 0):
                divergent = True
    return CvdState(cvd_sum=cvd_sum, cvd_abs_sum=cvd_abs_sum, cvd_divergent=divergent)


def mtf_boost_at(
    signal_trend: int,
    macro_regime_label: str,
) -> MtfBoostState:
    """
    Multi-timeframe boost: True when the signal-TF trend direction aligns
    with the macro regime direction.

    BULL_TREND/BULLISH/BULL_TRENDING → direction = 1
    BEAR_TREND/BEARISH/BEAR_TRENDING → direction = -1
    Everything else (RANGING, IDLE, VOLATILE, NEUTRAL, CHOPPY) → 0
    """
    if signal_trend == 0 or not macro_regime_label:
        return MtfBoostState(aligned=False)
    upper = macro_regime_label.upper()
    if "BULL" in upper:
        macro_dir = 1
    elif "BEAR" in upper:
        macro_dir = -1
    else:
        macro_dir = 0
    return MtfBoostState(aligned=macro_dir != 0 and signal_trend == macro_dir)


def staleness_lookback_at(
    st1_trend: np.ndarray,
    st2_trend: np.ndarray,
    st3_trend: np.ndarray,
    trend: int,
    st_threshold: int,
    thresholds: SignalThresholds,
    atr_percentile: float = 50.0,
) -> int:
    """
    Count consecutive prior bars whose ST trend count >= threshold in the
    same direction as `trend`. Returns the full lookback (default 16) when
    all looked-back bars matched — the legacy "for-else" branch.

    Used to apply a staleness penalty to old, "chase" entries that come long
    after the original flip — those have the worst forward R:R.

    Volatility-adaptive: when atr_percentile is provided, the effective lookback
    scales inversely with volatility. Low vol (slow moves) → shorter effective
    lookback → same bar count = more staleness = higher penalty. High vol →
    longer effective lookback → lower penalty. Formula:
        effective_lookback = staleness_lookback * max(0.5, min(2.0, 50 / atr_pct))
    clamped to [8, 32].
    """
    if trend == 0:
        return 0
    n_arr = len(st1_trend)
    if n_arr < 2:
        return 0

    base_lookback = thresholds.staleness_lookback
    if atr_percentile is not None and atr_percentile > 0:
        factor = max(0.5, min(2.0, 50.0 / float(atr_percentile)))
        effective_lookback = int(round(base_lookback * factor))
        effective_lookback = max(8, min(32, effective_lookback))
    else:
        effective_lookback = base_lookback

    direction_count = 1 if trend == 1 else -1
    bars_active = 0
    completed = True
    upper = n_arr - 2
    lower = max(-1, n_arr - 2 - effective_lookback)
    for j in range(upper, lower, -1):
        gc_prev = (
            int(st1_trend[j] == direction_count)
            + int(st2_trend[j] == direction_count)
            + int(st3_trend[j] == direction_count)
        )
        if gc_prev >= st_threshold:
            bars_active += 1
        else:
            completed = False
            break
    return thresholds.staleness_lookback if completed else bars_active


def rsi_extreme_at(
    rsi_values: np.ndarray,
    current_rsi: float,
    direction: int,
    lookback: int = _RSI_EXTREME_LOOKBACK,
    percentile: float = 0.10,
) -> tuple[bool, float]:
    """
    Adaptive RSI extreme gate using percentile rank instead of fixed thresholds.

    For short entries (direction=-1): extreme when current_rsi is above the
    (1 - percentile) threshold of the trailing `lookback` window.
    For long entries (direction=1): extreme when current_rsi is below the
    `percentile` threshold.

    Returns (is_extreme: bool, extremity_score: 0..1) where the score is
    linear in the gap between current value and the percentile threshold,
    saturating at 2× the threshold gap.

    Falls back to (False, 0.0) when the window is too small for a meaningful
    percentile estimate.
    """
    if rsi_values.size < 20 or current_rsi <= 0:
        return False, 0.0
    window = rsi_values[-lookback:]
    if direction == -1:
        thresh = float(np.percentile(window, (1.0 - percentile) * 100.0))
        extreme = current_rsi > thresh
        gap = max(0.0, current_rsi - thresh)
    else:
        thresh = float(np.percentile(window, percentile * 100.0))
        extreme = current_rsi < thresh
        gap = max(0.0, thresh - current_rsi)
    score = min(1.0, gap / max(1.0, abs(thresh) * 0.1)) if extreme else 0.0
    return extreme, score


# ── Score assembly ───────────────────────────────────────────────────────

def assemble_signal_score(
    *,
    flip:     FlipState,
    rsi:      RsiState,
    sq:       SqueezeState,
    vol:      VolumeState,
    ha:       HaState,
    cvd:      CvdState,
    mtf:      MtfBoostState,
    bars_active: int,
    thresholds: SignalThresholds,
    regime_label: str = "",
) -> Tuple[float, str, float, float]:
    """
    Compute (signal_score, signal_strength, earned, total_weight).

    `signal_score` is on the conventional 0..20 scale (= pct * 20).
    `signal_strength` is "STRONG" / "SIGNAL" / "NONE" via the configured
    pct thresholds.

    When `regime_label` matches a v4 regime profile and the thresholds
    request it, the per-flag weights are rescaled before earning. The total
    weight changes accordingly so the 0..1 pct scale remains stable.
    """
    if thresholds.use_regime_profiles and regime_label:
        from app.engines.directional.signal_weights import regime_aware_weights
        w = regime_aware_weights(regime_label)
    else:
        w = dict(thresholds.weights)
    total_weight = float(sum(w.values()))

    # Direction-correct fresh arrow: green_arrow for long, red_arrow for short.
    st_flip = (
        flip.green_arrow if flip.trend == 1
        else flip.red_arrow if flip.trend == -1
        else False
    )

    earned = 0.0
    if st_flip:        earned += w["st_flip"]
    if rsi.rsi_ok:     earned += w["rsi"]
    if rsi.rsi_momentum: earned += w["rsi_momentum"]
    if sq.squeeze_ok:  earned += w["squeeze"]
    if vol.vol_spike:  earned += w["volume"]
    if ha.ha_aligned:  earned += w["ha_aligned"]
    if ha.ha_real_aligned: earned += w["ha_real_aligned"]
    if mtf.aligned:    earned += w.get("mtf_boost", 0)

    stale_pen = min(thresholds.staleness_max, bars_active // thresholds.staleness_divisor)
    cvd_pen   = thresholds.cvd_divergence_penalty if cvd.cvd_divergent else 0.0

    # Signal coherence penalty: penalize mixed ST channel agreement.
    # When flip.st_trends shows disagreement, deduct up to 2.0 from earned.
    coh_pen = coherence_penalty(
        compute_coherence(list(flip.st_trends)),
        max_penalty=float(thresholds.staleness_max),
    )

    earned_adj = max(0.0, earned - stale_pen - cvd_pen - coh_pen)

    pct = earned_adj / total_weight if total_weight > 0 else 0.0
    if pct >= thresholds.strong_pct:
        strength = "STRONG"
    elif pct >= thresholds.signal_pct:
        strength = "SIGNAL"
    else:
        strength = "NONE"
    return round(pct * 20.0, 2), strength, earned_adj, total_weight
