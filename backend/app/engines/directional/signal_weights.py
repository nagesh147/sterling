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


# ── Base weights (sum to 20 by convention; signal_score is pct * 20) ──────
#
# Rebalanced from the two competing pre-v4 sets:
#
#   knob              vectorizer   signal_engine   v4 (this file)
#   st_flip                 3            5              4
#   rsi                     2            3              2
#   rsi_momentum            1            3              2
#   squeeze                 4            3              3
#   volume                  4            2              3
#   ha_aligned              4            2              3
#   ha_real_aligned         2            2              3
#   TOTAL                  20           20             20
#
# Rationale: st_flip slightly favoured because clean reversal entries
# dominate forward returns; ha_real_aligned weighted equal to ha_aligned
# because the divergence signal is what catches HA-smoothing during chop;
# rsi_momentum elevated so a 60+ RSI gets rewarded for being "in the
# trend" rather than just "in the band".
V4_BASE_WEIGHTS: Dict[str, int] = {
    "st_flip":         4,
    "rsi":             2,
    "rsi_momentum":    2,
    "squeeze":         3,
    "volume":          3,
    "ha_aligned":      3,
    "ha_real_aligned": 3,
}

V4_TOTAL_WEIGHT: int = sum(V4_BASE_WEIGHTS.values())  # 20


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
# Calibration note: initial v4 used larger multipliers (1.25/1.20) but
# baseline showed they *inflated* IDLE-bar scores enough to double the IDLE
# trade count on BTC 1h (33 → 69), with the new entries averaging −0.12%.
# Smaller multipliers (≤ 1.10) preserve the regime intent without blowing
# past the IDLE-bypass score_min in setup_engine. Empty profiles fall back
# to V4_BASE_WEIGHTS — used for regimes where the gate is enforced
# elsewhere (IDLE / CHOPPY get a hard score_min in setup_engine).
# v4 — initial experiment with multiplicative regime profiles (1.10-1.30
# multipliers on flags matched to the regime intent) showed regression on
# BTC intraday_1h: BEAR_TREND trade count grew 33 → 45 with avg PnL dropping
# from +0.22% to +0.10% — the boost was admitting marginal signals into the
# winning regime. Disabling regime profiles entirely and relying on the
# cost-aware + MTF-disagreement uplift in the entry condition produced
# cleaner results in baselines. Kept as an empty dict so the wiring stays
# in place; future calibration can re-enable specific regime tweaks.
V4_REGIME_PROFILES: Dict[str, Dict[str, float]] = {
    "BULL_TREND":    {},
    "BULLISH":       {},
    "BULL_TRENDING": {},
    "BEAR_TREND":    {},
    "BEARISH":       {},
    "BEAR_TRENDING": {},
    "VOLATILE":      {},
    "RANGING":       {},
    "NEUTRAL":       {},
    "IDLE":          {},  # hard score_min in setup_engine
    "CHOPPY":        {},  # hard score_min in setup_engine
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
