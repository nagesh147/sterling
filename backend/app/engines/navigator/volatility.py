"""Volatility regime + directional read (spec §9). STERLING-DESIGNED; every
weight/threshold is CALIBRATION-REQUIRED — the source only describes the
target behavior (EXPANSION/COMPRESSION/NEUTRAL, LONG/SHORT/WAIT, compression
forces WAIT for trend trades).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.indicators.atr import compute_atr
from app.engines.indicators.bollinger import bollinger_bands
from app.engines.indicators.ema import compute_ema
from app.engines.navigator.quality import ValidatedCandles

MODEL_VERSION = "volatility_v1"
EPSILON = 1e-9
_BARS_PER_YEAR_1H = 6 * 252  # ~6 NSE cash 1H bars/session, 252 sessions/year — diagnostic only

VolRegime = Literal["EXPANSION", "COMPRESSION", "NEUTRAL"]
VolDirection = Literal["LONG", "SHORT", "WAIT"]


# ── ADX / +DI / -DI (local: existing adx.py doesn't expose +DI/-DI) ──────

def _adx_di(high: NDArray[np.float64], low: NDArray[np.float64], close: NDArray[np.float64], period: int):
    n = len(close)
    zeros = np.zeros(n)
    if n < period * 2 + 1:
        return zeros.copy(), zeros.copy(), zeros.copy()

    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(1, n):
        h_diff = high[i] - high[i - 1]
        l_diff = low[i - 1] - low[i]
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        plus_dm[i] = h_diff if h_diff > l_diff and h_diff > 0 else 0.0
        minus_dm[i] = l_diff if l_diff > h_diff and l_diff > 0 else 0.0

    def _wilder(arr: NDArray[np.float64]) -> NDArray[np.float64]:
        out = np.zeros(n)
        out[period] = float(np.sum(arr[1:period + 1]))
        for i in range(period + 1, n):
            out[i] = out[i - 1] - out[i - 1] / period + arr[i]
        return out

    atr14 = _wilder(tr)
    pdm14 = _wilder(plus_dm)
    mdm14 = _wilder(minus_dm)

    with np.errstate(invalid="ignore", divide="ignore"):
        plus_di = np.where(atr14 > 0, 100.0 * pdm14 / atr14, 0.0)
        minus_di = np.where(atr14 > 0, 100.0 * mdm14 / atr14, 0.0)
        di_sum = plus_di + minus_di
        dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)

    adx = np.zeros(n)
    start = period * 2
    if start < n:
        adx[start] = float(np.mean(dx[period:period * 2 + 1]))
        for i in range(start + 1, n):
            adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
    return adx, plus_di, minus_di


# ── features (spec §9.1) ─────────────────────────────────────────────────

@dataclass(frozen=True)
class VolatilityFeatures:
    atr: NDArray[np.float64]
    atr_pct: NDArray[np.float64]
    rv_short: NDArray[np.float64]
    rv_long: NDArray[np.float64]
    rv_ratio: NDArray[np.float64]
    bandwidth: NDArray[np.float64]
    vol_gradient: NDArray[np.float64]
    adx: NDArray[np.float64]
    plus_di: NDArray[np.float64]
    minus_di: NDArray[np.float64]
    ema_fast: NDArray[np.float64]
    ema_slow: NDArray[np.float64]
    ema_fast_slope: NDArray[np.float64]
    warmup_index: int  # first index at which every feature above is valid


def _robust_slope(x: NDArray[np.float64], k: int) -> NDArray[np.float64]:
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(k, n):
        if np.isnan(x[t]) or np.isnan(x[t - k]):
            continue
        out[t] = (x[t] - x[t - k]) / k
    return out


def _log_returns(close: NDArray[np.float64]) -> NDArray[np.float64]:
    n = len(close)
    out = np.full(n, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        out[1:] = np.log(close[1:] / close[:-1])
    return out


def _rolling_std(x: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(window, n):
        seg = x[t - window + 1:t + 1]
        if np.any(np.isnan(seg)):
            continue
        out[t] = float(np.std(seg, ddof=1)) if window > 1 else 0.0
    return out


def compute_features(candles: ValidatedCandles, config) -> VolatilityFeatures:
    close = candles.close
    n = candles.n

    atr_arr = compute_atr(candles.high, candles.low, close, config.atr_period)
    atr_arr = atr_arr.astype(np.float64).copy()
    atr_arr[: config.atr_period] = np.nan
    with np.errstate(invalid="ignore", divide="ignore"):
        atr_pct = atr_arr / close

    log_ret = _log_returns(close)
    annualization = np.sqrt(_BARS_PER_YEAR_1H)
    rv_short = _rolling_std(log_ret, config.rv_short_bars) * annualization
    rv_long = _rolling_std(log_ret, config.rv_long_bars) * annualization
    with np.errstate(invalid="ignore", divide="ignore"):
        rv_ratio = rv_short / np.where(rv_long > EPSILON, rv_long, EPSILON)

    lower_band, mid_band, upper_band = bollinger_bands(close, config.band_period, config.band_stddev)
    bandwidth = np.full(n, np.nan)
    valid_band = mid_band != 0
    bandwidth[valid_band] = (upper_band[valid_band] - lower_band[valid_band]) / mid_band[valid_band]
    bandwidth[:config.band_period - 1] = np.nan

    vol_gradient = _robust_slope(atr_pct, config.gradient_bars)

    adx_arr, plus_di, minus_di = _adx_di(candles.high, candles.low, close, config.adx_period)
    adx_warmup = config.adx_period * 2

    ema_fast = compute_ema(close, config.ema_fast_period)
    ema_slow = compute_ema(close, config.ema_slow_period)
    ema_fast_slope = _robust_slope(ema_fast, config.gradient_bars)

    warmup_index = max(
        config.atr_period, config.rv_long_bars, config.band_period - 1,
        config.gradient_bars + config.atr_period, adx_warmup, config.ema_slow_period,
    )

    return VolatilityFeatures(
        atr=atr_arr, atr_pct=atr_pct, rv_short=rv_short, rv_long=rv_long, rv_ratio=rv_ratio,
        bandwidth=bandwidth, vol_gradient=vol_gradient, adx=adx_arr, plus_di=plus_di, minus_di=minus_di,
        ema_fast=ema_fast, ema_slow=ema_slow, ema_fast_slope=ema_fast_slope, warmup_index=warmup_index,
    )


# ── volatility score + regime (spec §9.2) ────────────────────────────────

def _rolling_percentile_rank(x: NDArray[np.float64], lookback: int, warmup_index: int) -> NDArray[np.float64]:
    """Percentile rank (0-100) of x[t] vs. the trailing `lookback` PRIOR
    values (t-lookback .. t-1) — never includes x[t] itself, so there is no
    leakage from the current bar into its own rank."""
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(warmup_index + 1, n):
        start = max(warmup_index, t - lookback)
        window = x[start:t]
        window = window[~np.isnan(window)]
        if len(window) < 5 or np.isnan(x[t]):
            continue
        out[t] = float(np.sum(x[t] > window) / len(window) * 100.0)
    return out


@dataclass(frozen=True)
class VolatilityScore:
    vol_score: NDArray[np.float64]
    regime_raw: list  # per-bar raw regime before hysteresis, VolRegime | None
    regime: list  # per-bar regime after hysteresis, VolRegime | None


def compute_score_and_regime(features: VolatilityFeatures, config) -> VolatilityScore:
    n = len(features.atr)
    atr_pct_rank = _rolling_percentile_rank(features.atr_pct, config.percentile_lookback, features.warmup_index)
    rv_ratio_rank = _rolling_percentile_rank(features.rv_ratio, config.percentile_lookback, features.warmup_index)
    bandwidth_rank = _rolling_percentile_rank(features.bandwidth, config.percentile_lookback, features.warmup_index)
    gradient_rank = _rolling_percentile_rank(features.vol_gradient, config.percentile_lookback, features.warmup_index)

    vol_score = np.full(n, np.nan)
    for t in range(n):
        parts = [atr_pct_rank[t], rv_ratio_rank[t], bandwidth_rank[t], gradient_rank[t]]
        if any(np.isnan(p) for p in parts):
            continue
        vol_score[t] = 0.35 * parts[0] + 0.25 * parts[1] + 0.20 * parts[2] + 0.20 * parts[3]

    regime_raw: list = [None] * n
    for t in range(n):
        if np.isnan(vol_score[t]) or np.isnan(features.vol_gradient[t]):
            continue
        if vol_score[t] >= config.expansion_min and features.vol_gradient[t] > 0:
            regime_raw[t] = "EXPANSION"
        elif vol_score[t] <= config.compression_max and features.vol_gradient[t] <= 0:
            regime_raw[t] = "COMPRESSION"
        else:
            regime_raw[t] = "NEUTRAL"

    # Hysteresis: require 2 consecutive bars agreeing before flipping the
    # displayed regime, unless the score is well past the threshold (an
    # "extreme" crossing, CALIBRATION-REQUIRED buffer of 15 points here).
    extreme_buffer = 15.0
    regime: list = [None] * n
    for t in range(n):
        if regime_raw[t] is None:
            continue
        if t == 0 or regime[t - 1] is None:
            regime[t] = regime_raw[t]
            continue
        if regime_raw[t] == regime[t - 1]:
            regime[t] = regime[t - 1]
            continue
        is_extreme = (
            vol_score[t] >= config.expansion_min + extreme_buffer
            or vol_score[t] <= config.compression_max - extreme_buffer
        )
        confirmed_by_prior_bar = regime_raw[t - 1] == regime_raw[t]
        if is_extreme or confirmed_by_prior_bar:
            regime[t] = regime_raw[t]
        else:
            regime[t] = regime[t - 1]

    return VolatilityScore(vol_score=vol_score, regime_raw=regime_raw, regime=regime)


# ── direction + confidence (spec §9.3-9.4) ───────────────────────────────

@dataclass(frozen=True)
class VolatilityEvaluation:
    regime: Optional[VolRegime]
    direction: VolDirection
    confidence_100: float
    flip_age_bars: Optional[int]
    late_flip: bool
    reason_codes: list
    diagnostics: dict


def _votes_at(t: int, features: VolatilityFeatures, close: NDArray[np.float64], config, mid_avwap: Optional[float], base_direction: Optional[str]) -> list[int]:
    votes: list[int] = []
    if not np.isnan(features.ema_fast[t]) and not np.isnan(features.ema_slow[t]) and features.ema_fast[t] != features.ema_slow[t]:
        votes.append(1 if features.ema_fast[t] > features.ema_slow[t] else -1)
    if not np.isnan(features.adx[t]) and features.adx[t] >= config.adx_min:
        if features.plus_di[t] != features.minus_di[t]:
            votes.append(1 if features.plus_di[t] > features.minus_di[t] else -1)
    if mid_avwap is not None and not np.isnan(mid_avwap) and close[t] != mid_avwap:
        votes.append(1 if close[t] > mid_avwap else -1)
    if base_direction is not None:
        votes.append(1 if base_direction == "long" else -1)
    return votes


def _confirmed_direction_series(raw_votes: list[int], trend_confirm_bars: int) -> list[int]:
    """`raw_votes[t]` is the majority sign (-1/0/1) of that bar's votes.
    The confirmed series only adopts a NEW nonzero direction once the last
    `trend_confirm_bars` raw votes all agree on it; until then it holds the
    previous confirmed value (sticky), starting at 0."""
    n = len(raw_votes)
    confirmed = [0] * n
    for t in range(n):
        if t < trend_confirm_bars - 1:
            confirmed[t] = confirmed[t - 1] if t > 0 else 0
            continue
        window = raw_votes[t - trend_confirm_bars + 1:t + 1]
        if window and window[0] != 0 and all(v == window[0] for v in window):
            confirmed[t] = window[0]
        else:
            confirmed[t] = confirmed[t - 1] if t > 0 else 0
    return confirmed


def evaluate_volatility(
    candles: ValidatedCandles, config, *, mid_avwap: Optional[float] = None, base_direction: Optional[str] = None,
) -> VolatilityEvaluation:
    features = compute_features(candles, config)
    scored = compute_score_and_regime(features, config)
    n = candles.n
    t = n - 1

    if t < features.warmup_index or scored.regime[t] is None:
        return VolatilityEvaluation(
            regime=None, direction="WAIT", confidence_100=0.0, flip_age_bars=None, late_flip=False,
            reason_codes=["VOL_WARMING_UP"], diagnostics={"vol_score": None},
        )

    # `mid_avwap`/`base_direction` are CURRENT-only values (a single scalar
    # AVWAP reading and the base engine's live direction, not per-bar
    # history) — applying them to every historical bar would retroactively
    # compare old closes against today's AVWAP and inject today's signal
    # into the past, corrupting the confirmed-direction/flip-age series.
    # They are only valid context for the most recent (current) bar.
    raw_votes: list[int] = []
    for i in range(n):
        ctx_avwap = mid_avwap if i == t else None
        ctx_direction = base_direction if i == t else None
        vs = _votes_at(i, features, candles.close, config, ctx_avwap, ctx_direction)
        if not vs:
            raw_votes.append(0)
            continue
        total = sum(vs)
        raw_votes.append(1 if total > 0 else (-1 if total < 0 else 0))

    confirmed = _confirmed_direction_series(raw_votes, config.trend_confirm_bars)

    last_flip = 0
    for i in range(1, n):
        if confirmed[i] != confirmed[i - 1] and confirmed[i] != 0:
            last_flip = i
    flip_age_bars = t - last_flip
    late_flip = flip_age_bars > config.max_flip_age_bars

    regime = scored.regime[t]
    votes_now = _votes_at(t, features, candles.close, config, mid_avwap, base_direction)
    agreement = 0.0
    if votes_now and confirmed[t] != 0:
        agreeing = sum(1 for v in votes_now if v == confirmed[t])
        agreement = 100.0 * agreeing / len(votes_now)

    adx_strength = min(100.0, 100.0 * features.adx[t] / 50.0) if not np.isnan(features.adx[t]) else 0.0
    atr_val = features.atr[t] if features.atr[t] > 0 else EPSILON
    slope = features.ema_fast_slope[t] / atr_val if not np.isnan(features.ema_fast_slope[t]) else 0.0
    slope_strength = min(100.0, 100.0 * abs(slope) / 0.5)

    confidence = (agreement + adx_strength + slope_strength) / 3.0
    if regime == "EXPANSION":
        confidence += 10.0
    elif regime == "COMPRESSION":
        confidence -= 10.0
    if late_flip:
        confidence -= 20.0
    fading = not np.isnan(features.vol_gradient[t]) and features.vol_gradient[t] < 0
    if fading:
        confidence -= 10.0
    confidence = max(0.0, min(100.0, confidence))

    reason_codes: list[str] = []
    direction: VolDirection

    if regime == "COMPRESSION":
        direction = "WAIT"
        reason_codes.append("COMPRESSION_NO_TREND")
    elif confirmed[t] == 0:
        direction = "WAIT"
        reason_codes.append("TREND_FORMING_WAIT" if any(raw_votes[max(0, t - config.trend_confirm_bars):t + 1]) else "NO_DIRECTIONAL_EDGE")
    elif confidence < config.min_direction_confidence:
        direction = "WAIT"
        reason_codes.append("NO_DIRECTIONAL_EDGE")
    else:
        direction = "LONG" if confirmed[t] == 1 else "SHORT"
        reason_codes.append("BULLISH_EXPANSION" if (direction == "LONG" and regime == "EXPANSION") else
                             "BEARISH_EXPANSION" if (direction == "SHORT" and regime == "EXPANSION") else "OK")

    if late_flip and direction != "WAIT":
        reason_codes.append("LATE_AFTER_FLIP")
    if fading and direction != "WAIT":
        reason_codes.append("VOLATILITY_FADING")

    return VolatilityEvaluation(
        regime=regime, direction=direction, confidence_100=confidence,
        flip_age_bars=flip_age_bars, late_flip=late_flip, reason_codes=reason_codes,
        diagnostics={
            "vol_score": None if np.isnan(scored.vol_score[t]) else float(scored.vol_score[t]),
            "vol_gradient": None if np.isnan(features.vol_gradient[t]) else float(features.vol_gradient[t]),
            "adx": None if np.isnan(features.adx[t]) else float(features.adx[t]),
            "confirmed_direction": confirmed[t],
        },
    )
