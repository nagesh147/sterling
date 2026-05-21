"""
Sterling v4 — Signal Weights Single Source of Truth.

Confluence weights, RSI/volume thresholds, strength bands, and regime-aware
weight profiles. Imported by BOTH `signal_engine.compute_signal` (per-bar live
path) and `mtf_vectorizer.build_signals_full` (vectorised backtest path) so
the two never drift.

Pre-v4 the two modules each had their own copy: signal_engine used
{st_flip:5, rsi:3, ha_aligned:2, vol_spike_x:2.0, rsi_long_lo:48} while
mtf_vectorizer used {st_flip:3, rsi:2, ha_aligned:4, vol_spike_x:1.5,
rsi_long_lo:42}. Baselines therefore reflected one strategy, live another.
This module is the chokepoint that ends that divergence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


# ── Base weights (sum to 22; signal_score is pct * 20, pct = earned / total) ─
#
# v4.5 added mtf_boost (2 pts) — a new convergence knob that rewards signal-TF
# alignment with the macro regime direction. Total shift 20 → 22.
#
#   knob              vectorizer   signal_engine   v4.5 (this file)
#   st_flip                 3            5              4
#   rsi                     2            3              2
#   rsi_momentum            1            3              2
#   squeeze                 4            3              3
#   volume                  4            2              3
#   ha_aligned              4            2              3
#   ha_real_aligned         2            2              3
#   mtf_boost               -            -              2
#   TOTAL                  20           20             22
#
# Rationale: st_flip slightly favoured because clean reversal entries
# dominate forward returns; ha_real_aligned weighted equal to ha_aligned
# because the divergence signal is what catches HA-smoothing during chop;
# rsi_momentum elevated so a 60+ RSI gets rewarded for being "in the
# trend" rather than just "in the band"; mtf_boost adds macro/signal
# alignment as an independent feature signal.
V4_BASE_WEIGHTS: Dict[str, int] = {
    "st_flip":         4,
    "rsi":             2,
    "rsi_momentum":    2,
    "squeeze":         3,
    "volume":          3,
    "ha_aligned":      3,
    "ha_real_aligned": 3,
    "mtf_boost":       2,
}

V4_TOTAL_WEIGHT: int = sum(V4_BASE_WEIGHTS.values())  # 22


# ── Multi-TF boost weight ──────────────────────────────────────────────────
# Added weight for when signal-TF trend direction matches macro regime
# direction. A new knob added to the base weights below.
V4_MTF_BOOST_WEIGHT: int = 2


# ── RSI thresholds ────────────────────────────────────────────────────────
#
# rsi_long_lo lifted from the vectoriser's 42 to 48. At 42 the engine bought
# into still-bleeding pullbacks; the BTC 1h baseline showed BULL_TREND won
# only 44% of trades, the single biggest leak. 48 forces the entry only when
# the pullback has actually resolved upward.
#
# rsi_short_hi tightened from 57 to 52 — symmetric to the long change.
V4_RSI_LONG_LO:        float = 48.0
V4_RSI_LONG_HI:        float = 70.0
V4_RSI_SHORT_LO:       float = 30.0
V4_RSI_SHORT_HI:       float = 52.0

# Momentum bonus zone: in-trend RSI strong but not yet over/oversold.
V4_RSI_LONG_MOM_LO:    float = 55.0
V4_RSI_LONG_MOM_HI:    float = 68.0
V4_RSI_SHORT_MOM_LO:   float = 32.0
V4_RSI_SHORT_MOM_HI:   float = 45.0


# ── Volume gate ───────────────────────────────────────────────────────────
#
# Raised from the vectoriser's 1.5× to 2.0×. 1.5× sits inside crypto natural
# noise; 2.0× is documented institutional flow. Trade count drops; quality
# rises.
V4_VOL_SPIKE_MULT:     float = 2.0

# Volume z-score alternative: instead of vol > mult * median, flag when
# vol exceeds mean by this many standard deviations within the window.
# 2.0σ = top ~2.5% in a normal distribution (fewer, cleaner climax signals).
V4_VOL_ZSCORE_THRESHOLD: float = 2.0


# ── Squeeze (BB inside KC) ────────────────────────────────────────────────
V4_BB_PERIOD:          int   = 20
V4_BB_STD:             float = 2.0
V4_KC_PERIOD:          int   = 20
V4_KC_ATR_PERIOD:      int   = 10
V4_KC_MULT:            float = 1.5


# ── HA/Real divergence threshold ─────────────────────────────────────────
V4_HA_REAL_DIV_PCT:    float = 0.3


# ── CVD divergence penalty ────────────────────────────────────────────────
V4_CVD_WINDOW:               int   = 10
V4_CVD_DIVERGENCE_RATIO:     float = 0.5
V4_CVD_DIVERGENCE_PENALTY:   float = 3.0


# ── Staleness ─────────────────────────────────────────────────────────────
V4_STALENESS_LOOKBACK: int   = 16
V4_STALENESS_DIVISOR:  int   = 5
V4_STALENESS_MAX:      int   = 3


# ── Strength banding (fraction of max earned score) ───────────────────────
V4_STRENGTH_STRONG_PCT: float = 0.75
V4_STRENGTH_SIGNAL_PCT: float = 0.35


# ── Regime-aware weight profiles ──────────────────────────────────────────
#
# Multiplicative adjustments on V4_BASE_WEIGHTS keyed by macro_regime.value.
# Used by `regime_aware_weights()` below.
#
# Calibration notes:
# BULL_TREND: trend-following regime — boost st_flip + HA (trend features),
#             hold RSI/momentum/volume neutral. mtf_boost gets ×1.5 since
#             alignment with macro is the entire thesis.
# BEAR_TREND: symmetric boost but CVD ×1.2 (short-side CVD divergence is
#             more reliable for detecting fake breakdowns).
# VOLATILE:   squeeze ×1.5, volume ×1.5 — breakout features dominate.
#             mtf_boost gets ×0.5 because VOLATILE signals are short-lived
#             and macro alignment adds less edge.
# RANGING:    RSI ×1.3, mtf_boost ×0.5 (mean-reversion, MTF not meaningful).
# IDLE/CHOPPY: all ×0.5 — suppress everything. The hard score_min in
#             setup_engine is the primary gate; profiles are the secondary.
V4_REGIME_PROFILES: Dict[str, Dict[str, float]] = {
    "BULL_TREND":    {"st_flip": 1.2, "ha_aligned": 1.2, "mtf_boost": 1.5},
    "BULLISH":       {"st_flip": 1.1, "ha_aligned": 1.1, "mtf_boost": 1.3},
    "BULL_TRENDING": {"st_flip": 1.2, "ha_aligned": 1.2, "mtf_boost": 1.5},
    "BEAR_TREND":    {"st_flip": 1.2, "cvd": 1.2, "mtf_boost": 1.5},
    "BEARISH":       {"st_flip": 1.1, "cvd": 1.1, "mtf_boost": 1.3},
    "BEAR_TRENDING": {"st_flip": 1.2, "cvd": 1.2, "mtf_boost": 1.5},
    "VOLATILE":      {"squeeze": 1.5, "volume": 1.5, "mtf_boost": 0.5},
    "RANGING":       {"rsi": 1.3, "volume": 1.3, "mtf_boost": 0.5},
    "NEUTRAL":       {"rsi": 1.2, "volume": 1.2, "mtf_boost": 0.5},
    "IDLE":          {"st_flip": 0.5, "rsi": 0.5, "rsi_momentum": 0.5, "squeeze": 0.5, "volume": 0.5, "ha_aligned": 0.5, "ha_real_aligned": 0.5, "mtf_boost": 0.5},
    "CHOPPY":        {"st_flip": 0.5, "rsi": 0.5, "rsi_momentum": 0.5, "squeeze": 0.5, "volume": 0.5, "ha_aligned": 0.5, "ha_real_aligned": 0.5, "mtf_boost": 0.5},
}


def regime_aware_weights(regime_label: Optional[str]) -> Dict[str, int]:
    """
    Return the effective weight dict for a given macro regime label.

    Multiplies V4_BASE_WEIGHTS by the regime's multiplier profile and rounds
    to int. Total weight may differ from 20 after adjustment — `score_pct`
    consumers should always divide earned by the dict's own total, not the
    base 20, so the regime shift doesn't break the 0..1 scale.

    Unknown regimes return the base weights unchanged.
    """
    if not regime_label:
        return dict(V4_BASE_WEIGHTS)
    profile = V4_REGIME_PROFILES.get(regime_label)
    if not profile:
        return dict(V4_BASE_WEIGHTS)
    out: Dict[str, int] = {}
    for k, w in V4_BASE_WEIGHTS.items():
        mult = profile.get(k, 1.0)
        out[k] = max(1, int(round(w * mult)))
    return out


@dataclass(frozen=True)
class SignalThresholds:
    """
    Bundle of all confluence knobs. Callers can override any field by passing
    a custom instance to `compute_signal` / `build_signals_full`. The dataclass
    is frozen so accidental mutation across calls is impossible.

    Defaults are the V4 baseline above. Tests construct overrides to verify
    boundary behaviour without touching globals.
    """
    weights:                Dict[str, int] = field(default_factory=lambda: dict(V4_BASE_WEIGHTS))
    rsi_long_lo:            float = V4_RSI_LONG_LO
    rsi_long_hi:            float = V4_RSI_LONG_HI
    rsi_short_lo:           float = V4_RSI_SHORT_LO
    rsi_short_hi:           float = V4_RSI_SHORT_HI
    rsi_long_mom_lo:        float = V4_RSI_LONG_MOM_LO
    rsi_long_mom_hi:        float = V4_RSI_LONG_MOM_HI
    rsi_short_mom_lo:       float = V4_RSI_SHORT_MOM_LO
    rsi_short_mom_hi:       float = V4_RSI_SHORT_MOM_HI
    vol_spike_mult:         float = V4_VOL_SPIKE_MULT
    vol_zscore_threshold:   float = V4_VOL_ZSCORE_THRESHOLD
    mtf_boost_weight:       int   = V4_MTF_BOOST_WEIGHT
    bb_period:              int   = V4_BB_PERIOD
    bb_std:                 float = V4_BB_STD
    kc_period:              int   = V4_KC_PERIOD
    kc_atr_period:          int   = V4_KC_ATR_PERIOD
    kc_mult:                float = V4_KC_MULT
    ha_real_div_pct_max:    float = V4_HA_REAL_DIV_PCT
    cvd_window:             int   = V4_CVD_WINDOW
    cvd_divergence_ratio:   float = V4_CVD_DIVERGENCE_RATIO
    cvd_divergence_penalty: float = V4_CVD_DIVERGENCE_PENALTY
    staleness_lookback:     int   = V4_STALENESS_LOOKBACK
    staleness_divisor:      int   = V4_STALENESS_DIVISOR
    staleness_max:          int   = V4_STALENESS_MAX
    strong_pct:             float = V4_STRENGTH_STRONG_PCT
    signal_pct:             float = V4_STRENGTH_SIGNAL_PCT
    use_regime_profiles:    bool  = True


DEFAULT_THRESHOLDS = SignalThresholds()
