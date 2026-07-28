"""Option-flow oscillator (spec §11). Behavior SOURCE-DEFINED (a zero-
centered oscillator; positive bullish, negative bearish); formula
STERLING-DESIGNED; thresholds CALIBRATION-REQUIRED.

OI and price never reveal aggressor identity here — OI only contributes
*activity/confirmation intensity*, never an inferred buy/write side.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.navigator.avwap import _confirmed_pivots

MODEL_VERSION = "option_flow_v1"
EPSILON = 1e-9

FlowState = Literal["bullish", "bearish", "neutral"]


@dataclass(frozen=True)
class ContractFlowInput:
    """One contract's inputs for one sample. `delta_volume`/`delta_oi` come
    from `chain_sampler.compute_counter_delta` — `None` means the counter
    isn't comparable this sample (warmup/reset/gap), and the contract is
    excluded from that sample's activity sum rather than treated as zero."""

    token: int
    option_type: Literal["CE", "PE"]
    strike: float
    mid: float
    prev_mid: Optional[float]
    delta_volume: Optional[int]
    delta_oi: Optional[int]
    spread_pct: Optional[float]  # (ask - bid) / mid; None when depth was unavailable


@dataclass(frozen=True)
class ChainFlowSample:
    sample_ms: int
    atm_strike: float
    strike_step: float
    contracts: list[ContractFlowInput]


def _oi_intensity(delta_oi: Optional[int]) -> Optional[float]:
    if delta_oi is None:
        return None
    return math.log1p(abs(delta_oi))


def _price_returns_pool(history: list[ChainFlowSample], upto_index: int, lookback: int) -> list[float]:
    """Pooled price-return history across ALL contracts in the trailing
    window, used as a single shared robust price scale (spec's formula
    gives one scale per contract; pooling across contracts within one
    underlying's chain is the Sterling-designed simplification — the
    config only exposes one window size, implying one shared estimator)."""
    pool: list[float] = []
    start = max(0, upto_index - lookback)
    for sample in history[start:upto_index]:
        for c in sample.contracts:
            if c.prev_mid and c.prev_mid > 0 and c.mid > 0:
                pool.append(math.log(c.mid / c.prev_mid))
    return pool


def _robust_scale(pool: list[float], floor: float) -> float:
    if not pool:
        return floor
    center = float(np.median(pool))
    mad = float(np.median(np.abs(np.array(pool) - center)))
    return max(1.4826 * mad, floor)


def _prior_oi_intensity_pool(history: list[ChainFlowSample], upto_index: int, lookback: int) -> list[float]:
    pool: list[float] = []
    start = max(0, upto_index - lookback)
    for sample in history[start:upto_index]:
        for c in sample.contracts:
            v = _oi_intensity(c.delta_oi)
            if v is not None:
                pool.append(v)
    return pool


def _percentile_rank_01(value: float, pool: list[float]) -> float:
    if not pool:
        return 0.5
    return sum(1 for p in pool if value > p) / len(pool)


@dataclass(frozen=True)
class RawActivityResult:
    raw_activity: float
    call_activity: float
    put_activity: float
    valid_contracts: int


def compute_raw_activity(history: list[ChainFlowSample], index: int, config) -> RawActivityResult:
    """One sample's aggregate directional activity (spec §11.1)."""
    sample = history[index]
    price_scale = _robust_scale(
        _price_returns_pool(history, index, config.robust_window_samples), config.price_scale_floor
    )
    oi_pool = _prior_oi_intensity_pool(history, index, config.robust_window_samples)
    strike_scale = max(sample.strike_step * 2.0, config.price_scale_floor)

    total = 0.0
    call_total = 0.0
    put_total = 0.0
    valid = 0
    for c in sample.contracts:
        if c.prev_mid is None or c.prev_mid <= 0 or c.mid <= 0 or c.delta_volume is None:
            continue
        side = 1.0 if c.option_type == "CE" else -1.0
        price_return = math.log(c.mid / c.prev_mid)
        price_impulse = math.tanh(price_return / price_scale)
        volume_intensity = math.log1p(max(0, c.delta_volume))
        oi_int = _oi_intensity(c.delta_oi)
        norm_oi = _percentile_rank_01(oi_int, oi_pool) if oi_int is not None else 0.0
        proximity = math.exp(-abs(c.strike - sample.atm_strike) / strike_scale)
        spread_pct = c.spread_pct if c.spread_pct is not None else 1.0
        liquidity = max(0.0, min(1.0, 1.0 - spread_pct / max(config.max_spread_pct, EPSILON)))

        activity = (
            side * price_impulse * volume_intensity
            * (1.0 + config.oi_intensity_weight * norm_oi)
            * proximity * liquidity
        )
        total += activity
        valid += 1
        if side > 0:
            call_total += activity
        else:
            put_total += activity

    return RawActivityResult(raw_activity=total, call_activity=call_total, put_activity=put_total, valid_contracts=valid)


def compute_oscillator_series(raw_activities: list[float], config) -> list[float]:
    """Robust rolling normalization (spec §11.2). NaN before `warmup_samples`."""
    n = len(raw_activities)
    out = [float("nan")] * n
    for t in range(n):
        window = raw_activities[max(0, t - config.robust_window_samples + 1):t + 1]
        if len(window) < config.warmup_samples:
            continue
        center = float(np.median(window))
        scale = max(1.4826 * float(np.median(np.abs(np.array(window) - center))), EPSILON)
        z = (raw_activities[t] - center) / scale
        out[t] = 100.0 * math.tanh(z / config.z_scale)
    return out


def apply_zero_hysteresis(oscillator: list[float], hysteresis: float) -> list[FlowState]:
    """Bullish only after crossing +hysteresis, bearish only after crossing
    -hysteresis; retains the prior state inside the band."""
    states: list[FlowState] = []
    current: FlowState = "neutral"
    for v in oscillator:
        if not math.isnan(v):
            if v >= hysteresis:
                current = "bullish"
            elif v <= -hysteresis:
                current = "bearish"
        states.append(current)
    return states


def detect_divergence(
    price_close: list[float], oscillator: list[float], *,
    pivot_left_bars: int, pivot_right_bars: int, min_separation_bars: int, min_oscillator_magnitude: float,
) -> Optional[str]:
    """Optional advisory evidence. Uses CONFIRMED price pivots — the same
    right-bar confirmation / no-backfill rule as AVWAP — and reads the
    already-computed oscillator value at those same confirmed bar indices
    (which, by construction, never used information from after that bar).
    Never labels an unconfirmed current extremum as divergence."""
    price_arr = np.asarray(price_close, dtype=float)
    n = len(price_close)
    highs = _confirmed_pivots(price_arr, pivot_left_bars, pivot_right_bars, "high")
    lows = _confirmed_pivots(price_arr, pivot_left_bars, pivot_right_bars, "low")

    def _osc_at(idx: int) -> Optional[float]:
        v = oscillator[idx]
        return None if math.isnan(v) else v

    visible_highs = [p for p in highs if p.visible_from_index < n]
    if len(visible_highs) >= 2:
        a, b = visible_highs[-2], visible_highs[-1]
        if b.bar_index - a.bar_index >= min_separation_bars:
            oa, ob = _osc_at(a.bar_index), _osc_at(b.bar_index)
            if (
                oa is not None and ob is not None
                and abs(oa) >= min_oscillator_magnitude and abs(ob) >= min_oscillator_magnitude
                and b.price > a.price and ob < oa
            ):
                return "BEARISH_DIVERGENCE"

    visible_lows = [p for p in lows if p.visible_from_index < n]
    if len(visible_lows) >= 2:
        a, b = visible_lows[-2], visible_lows[-1]
        if b.bar_index - a.bar_index >= min_separation_bars:
            oa, ob = _osc_at(a.bar_index), _osc_at(b.bar_index)
            if (
                oa is not None and ob is not None
                and abs(oa) >= min_oscillator_magnitude and abs(ob) >= min_oscillator_magnitude
                and b.price < a.price and ob > oa
            ):
                return "BULLISH_DIVERGENCE"
    return None


@dataclass(frozen=True)
class OptionFlowEvaluation:
    oscillator: Optional[float]
    state: FlowState
    direction: Literal[-1, 0, 1]
    confidence_100: float
    quality: Literal["ok", "degraded", "unavailable"]
    reason_codes: list[str]
    diagnostics: dict


def evaluate_option_flow(
    history: list[ChainFlowSample], config, *, chain_quality: Literal["ok", "degraded", "unavailable"] = "ok",
) -> OptionFlowEvaluation:
    if not history:
        return OptionFlowEvaluation(
            oscillator=None, state="neutral", direction=0, confidence_100=0.0,
            quality="unavailable", reason_codes=["CHAIN_UNAVAILABLE"], diagnostics={},
        )
    if chain_quality == "unavailable":
        return OptionFlowEvaluation(
            oscillator=None, state="neutral", direction=0, confidence_100=0.0,
            quality="unavailable", reason_codes=["CHAIN_UNAVAILABLE"], diagnostics={},
        )

    raw_results = [compute_raw_activity(history, i, config) for i in range(len(history))]
    raw_activities = [r.raw_activity for r in raw_results]
    oscillator_series = compute_oscillator_series(raw_activities, config)
    states = apply_zero_hysteresis(oscillator_series, config.zero_hysteresis)

    t = len(history) - 1
    osc_t = oscillator_series[t]
    state_t = states[t]

    if math.isnan(osc_t):
        return OptionFlowEvaluation(
            oscillator=None, state="neutral", direction=0, confidence_100=0.0,
            quality="unavailable", reason_codes=["FLOW_WARMING_UP"], diagnostics={"valid_contracts": raw_results[t].valid_contracts},
        )

    direction: Literal[-1, 0, 1] = 1 if state_t == "bullish" else (-1 if state_t == "bearish" else 0)
    inside_band = abs(osc_t) < config.zero_hysteresis
    confidence = min(100.0, abs(osc_t))
    quality: Literal["ok", "degraded", "unavailable"] = "ok"
    reason_codes: list[str] = ["OK"]
    if chain_quality == "degraded":
        confidence *= 0.7
        quality = "degraded"
        reason_codes = ["CHAIN_INCOMPLETE"]
    if inside_band:
        confidence *= 0.5  # retained prior state, but inside the band -> lower confidence
        quality = "degraded" if quality == "ok" else quality

    return OptionFlowEvaluation(
        oscillator=float(osc_t), state=state_t, direction=direction, confidence_100=confidence,
        quality=quality, reason_codes=reason_codes,
        diagnostics={
            "raw_activity": raw_activities[t],
            "call_activity": raw_results[t].call_activity,
            "put_activity": raw_results[t].put_activity,
            "valid_contracts": raw_results[t].valid_contracts,
            "inside_hysteresis_band": inside_band,
        },
    )
