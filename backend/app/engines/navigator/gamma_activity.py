"""Gamma activity (spec §12). Behavior SOURCE-DEFINED (a gamma "blast/burst"
is confirmation/warning of unusual ATM activity, never a standalone buy/sell
command); formula STERLING-DESIGNED; thresholds CALIBRATION-REQUIRED.

This is **gross gamma activity**, not dealer gamma exposure — never call it
dealer GEX, and never reuse `gex_engine.py`'s hardcoded ±100,000 routing
scale (that constant is tuned for a completely different purpose and has no
statistical basis for Navigator's own normalization).

Uses its own clean-room fractional-time Black-Scholes gamma (via
`scipy.stats.norm`, unused elsewhere in the repo) rather than the existing
integer-DTE `bs_pricing.py` — that module is shared by GEX/greeks-budget and
assumes whole calendar-day DTE, which is invalid for expiry-day gamma.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Optional

import numpy as np
from scipy.stats import norm

from app.services.navigator.calendar import IST, expiry_close_ist

MODEL_VERSION = "gamma_activity_v1"
EPSILON = 1e-9

ExpiryProfile = Literal["non_expiry", "expiry_before_14_ist", "expiry_after_14_ist"]


# ── fractional time-to-expiry + clean-room BSM gamma (spec §12.1-12.2) ──

def fractional_time_to_expiry(quote_ts_ms: int, expiry_close_ts_ms: int) -> Optional[float]:
    """`T` in years from an EXACT expiry-close epoch timestamp — never
    integer calendar-day DTE. Returns None (never a fabricated small
    positive value) once `T` would be <= 0."""
    seconds = (expiry_close_ts_ms - quote_ts_ms) / 1000.0
    if seconds <= 0:
        return None
    return seconds / (365.0 * 24 * 3600)


def bs_gamma(spot: float, strike: float, T: Optional[float], iv: Optional[float], risk_free_rate: float, dividend_yield: float) -> Optional[float]:
    """Returns None for any invalid input — never a fabricated zero."""
    if spot <= 0 or strike <= 0 or T is None or T <= 0 or iv is None or iv <= 0:
        return None
    try:
        d1 = (
            math.log(spot / strike) + (risk_free_rate - dividend_yield + 0.5 * iv * iv) * T
        ) / (iv * math.sqrt(T))
    except (ValueError, ZeroDivisionError):
        return None
    denom = spot * iv * math.sqrt(T)
    if denom <= 0:
        return None
    return float(math.exp(-dividend_yield * T) * norm.pdf(d1) / denom)


# ── per-contract + per-sample activity (spec §12.3) ─────────────────────

@dataclass(frozen=True)
class GammaContractInput:
    token: int
    strike: float
    lot_size: int
    iv: Optional[float]
    delta_volume: Optional[int]
    price_return_sign: int  # sign of THIS contract's own price move this sample


@dataclass(frozen=True)
class GammaSampleResult:
    gross_gamma_activity: float
    signed_gamma_activity: float
    valid_contracts: int


def contract_gamma_notional(
    contract: GammaContractInput, *, spot: float, T: Optional[float],
    risk_free_rate: Optional[float], dividend_yield: Optional[float], min_iv: float, max_iv: float,
) -> Optional[float]:
    if contract.iv is None or not (min_iv <= contract.iv <= max_iv):
        return None
    if T is None or risk_free_rate is None or dividend_yield is None:
        return None
    if contract.delta_volume is None:
        return None
    gamma = bs_gamma(spot, contract.strike, T, contract.iv, risk_free_rate, dividend_yield)
    if gamma is None:
        return None
    return abs(gamma) * spot * spot * 0.01 * contract.lot_size * abs(contract.delta_volume)


def compute_gamma_sample(
    contracts: list[GammaContractInput], *, spot: float, T: Optional[float],
    risk_free_rate: Optional[float], dividend_yield: Optional[float], min_iv: float, max_iv: float,
) -> GammaSampleResult:
    gross = 0.0
    signed = 0.0
    valid = 0
    for c in contracts:
        notional = contract_gamma_notional(
            c, spot=spot, T=T, risk_free_rate=risk_free_rate, dividend_yield=dividend_yield,
            min_iv=min_iv, max_iv=max_iv,
        )
        if notional is None:
            continue
        gross += notional
        signed += c.price_return_sign * notional
        valid += 1
    return GammaSampleResult(gross_gamma_activity=gross, signed_gamma_activity=signed, valid_contracts=valid)


# ── robust level/acceleration z-scores + event detection ────────────────

def _robust_z(values: list[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    arr = np.asarray(values, dtype=float)
    center = float(np.median(arr))
    scale = max(1.4826 * float(np.median(np.abs(arr - center))), EPSILON)
    return (values[-1] - center) / scale


def compute_level_and_acceleration_z(gross_history: list[float], window: int) -> tuple[Optional[float], Optional[float]]:
    level_z = _robust_z(gross_history[-window:])
    diffs = [b - a for a, b in zip(gross_history[:-1], gross_history[1:])]
    accel_z = _robust_z(diffs[-window:]) if diffs else None
    return level_z, accel_z


def is_gamma_event(
    level_z: Optional[float], acceleration_z: Optional[float], *,
    blast_z_min: float, acceleration_z_min: float, chain_quality_ok: bool, sample_count: int, min_samples: int,
) -> bool:
    if level_z is None or acceleration_z is None or not chain_quality_ok or sample_count < min_samples:
        return False
    return level_z >= blast_z_min and acceleration_z >= acceleration_z_min


# ── expiry profile selection (spec §12.4) ───────────────────────────────

def classify_expiry_profile(quote_ts_ms: int, expiry_date: date, expiry_profile_start_ist: str) -> ExpiryProfile:
    """The clock only CHOOSES which baseline to compare against — it never
    creates a gamma event by itself."""
    now_ist = datetime.fromtimestamp(quote_ts_ms / 1000.0, tz=IST)
    if now_ist.date() != expiry_date:
        return "non_expiry"
    hh, mm = (int(x) for x in expiry_profile_start_ist.split(":"))
    cutoff = now_ist.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return "expiry_after_14_ist" if now_ist >= cutoff else "expiry_before_14_ist"


# ── top-level evaluation ─────────────────────────────────────────────────

@dataclass(frozen=True)
class GammaEvaluation:
    gross_gamma_activity: Optional[float]
    signed_gamma_activity: Optional[float]
    level_z: Optional[float]
    acceleration_z: Optional[float]
    is_event: bool
    expiry_profile: ExpiryProfile
    direction: Literal[-1, 0, 1]
    confidence_100: float
    quality: Literal["ok", "degraded", "unavailable"]
    reason_codes: list[str]
    diagnostics: dict


def evaluate_gamma_activity(
    *,
    spot: float,
    contracts: list[GammaContractInput],
    quote_ts_ms: int,
    expiry_date: date,
    risk_free_rate: Optional[float],
    dividend_yield: Optional[float],
    profile_history: list[float],  # this profile's PRIOR gross-activity samples, oldest -> newest
    config,
    chain_quality: Literal["ok", "degraded", "unavailable"] = "ok",
    flow_direction: Literal[-1, 0, 1] = 0,
    flow_quality: Literal["ok", "degraded", "unavailable"] = "unavailable",
) -> GammaEvaluation:
    profile = classify_expiry_profile(quote_ts_ms, expiry_date, config.expiry_profile_start_ist)

    if risk_free_rate is None or dividend_yield is None:
        return GammaEvaluation(
            gross_gamma_activity=None, signed_gamma_activity=None, level_z=None, acceleration_z=None,
            is_event=False, expiry_profile=profile, direction=0, confidence_100=0.0,
            quality="unavailable", reason_codes=["CONFIG_INVALID"], diagnostics={"reason": "risk_free_rate/dividend_yield not set"},
        )

    expiry_close_ts_ms = int(expiry_close_ist(expiry_date).timestamp() * 1000)
    T = fractional_time_to_expiry(quote_ts_ms, expiry_close_ts_ms)
    if T is None:
        return GammaEvaluation(
            gross_gamma_activity=None, signed_gamma_activity=None, level_z=None, acceleration_z=None,
            is_event=False, expiry_profile=profile, direction=0, confidence_100=0.0,
            quality="unavailable", reason_codes=["EXPIRY_INVALID"], diagnostics={},
        )

    sample = compute_gamma_sample(
        contracts, spot=spot, T=T, risk_free_rate=risk_free_rate, dividend_yield=dividend_yield,
        min_iv=config.min_iv, max_iv=config.max_iv,
    )
    if sample.valid_contracts == 0:
        return GammaEvaluation(
            gross_gamma_activity=None, signed_gamma_activity=None, level_z=None, acceleration_z=None,
            is_event=False, expiry_profile=profile, direction=0, confidence_100=0.0,
            quality="unavailable", reason_codes=["IV_MISSING"], diagnostics={"T_years": T},
        )

    history_with_current = profile_history + [sample.gross_gamma_activity]
    if len(history_with_current) < config.min_samples:
        return GammaEvaluation(
            gross_gamma_activity=sample.gross_gamma_activity, signed_gamma_activity=sample.signed_gamma_activity,
            level_z=None, acceleration_z=None, is_event=False, expiry_profile=profile,
            direction=0, confidence_100=0.0, quality="unavailable", reason_codes=["GAMMA_WARMING_UP"],
            diagnostics={"valid_contracts": sample.valid_contracts, "profile_samples": len(history_with_current), "T_years": T},
        )

    level_z, acceleration_z = compute_level_and_acceleration_z(history_with_current, config.robust_window_samples)
    event = is_gamma_event(
        level_z, acceleration_z, blast_z_min=config.blast_z_min, acceleration_z_min=config.acceleration_z_min,
        chain_quality_ok=(chain_quality != "unavailable"), sample_count=len(history_with_current), min_samples=config.min_samples,
    )

    direction: Literal[-1, 0, 1] = 0
    reason_codes = ["OK"]
    if event and config.require_flow_alignment and flow_quality != "unavailable" and flow_direction != 0:
        direction = flow_direction  # gamma NEVER supplies direction on its own
    elif event:
        reason_codes = ["GAMMA_UNAVAILABLE_OPTIONAL"] if flow_quality == "unavailable" else ["OK"]

    confidence = min(100.0, max(0.0, (level_z or 0.0) * 10.0)) if event else 0.0
    quality: Literal["ok", "degraded", "unavailable"] = "ok" if chain_quality == "ok" else "degraded"

    return GammaEvaluation(
        gross_gamma_activity=sample.gross_gamma_activity, signed_gamma_activity=sample.signed_gamma_activity,
        level_z=level_z, acceleration_z=acceleration_z, is_event=event, expiry_profile=profile,
        direction=direction, confidence_100=confidence, quality=quality, reason_codes=reason_codes,
        diagnostics={"valid_contracts": sample.valid_contracts, "T_years": T, "profile_samples": len(history_with_current)},
    )
