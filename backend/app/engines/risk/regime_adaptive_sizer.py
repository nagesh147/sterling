"""
Sterling v4 — Regime-Adaptive Sizer

Multiplier wrapper around the fractional-Kelly base sizer. Reads ATR percentile
and applies the "fat barbell" sizing curve:

    < 25 pct  →  0.50×   (compression — slow moves, half-size)
    25–60 pct →  1.00×   (normal regime)
    60–85 pct →  1.25×   (healthy expansion — favourable trend)
    > 85 pct  →  0.75×   (hyper-expansion — gap risk, partial-size)

This is composable with the Kelly cap, the per-structure cap, and the global
position cap; the smallest cap wins (see SPEC §C3).

Pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AdaptiveSizingConfig:
    compression_pct:    float = 25.0    # below this → compression
    normal_lo_pct:      float = 25.0
    normal_hi_pct:      float = 60.0
    expansion_hi_pct:   float = 85.0    # above expansion_hi → hyper-expansion

    mult_compression:   float = 0.5
    mult_normal:        float = 1.0
    mult_healthy:       float = 1.25
    mult_hyper:         float = 0.75
    # Issue 4 — IDLE bucket multiplier. When the macro_regime is IDLE but the
    # caller wants to size *down* instead of veto entirely (loose mode), the
    # sizer applies this multiplier on top of the percentile-based one.
    mult_idle:          float = 0.25


def adapt(
    atr_percentile: Optional[float],
    config: Optional[AdaptiveSizingConfig] = None,
    *,
    is_idle: bool = False,
) -> float:
    """
    Returns the sizing multiplier keyed on ATR pct.

    When `is_idle=True` (Issue 4), returns `mult_idle` regardless of ATR pct
    so the caller can size IDLE bars down to ~0.25× instead of vetoing them.
    Default is_idle=False to preserve back-compat.

    When `atr_percentile is None` (insufficient candles to compute), returns
    1.0 — fail-open is correct here because the upstream Kelly + caps already
    bound the risk; this multiplier is an *enhancer*, not a *guard*.
    """
    cfg = config or AdaptiveSizingConfig()

    if is_idle:
        return cfg.mult_idle

    if atr_percentile is None:
        return 1.0

    p = float(atr_percentile)
    if p < cfg.compression_pct:
        return cfg.mult_compression
    if p <= cfg.normal_hi_pct:
        return cfg.mult_normal
    if p <= cfg.expansion_hi_pct:
        return cfg.mult_healthy
    return cfg.mult_hyper


def regime_label(atr_percentile: Optional[float],
                 config: Optional[AdaptiveSizingConfig] = None) -> str:
    """Human-readable label for the current regime. Used by UI badges."""
    cfg = config or AdaptiveSizingConfig()
    if atr_percentile is None:
        return "unknown"
    p = float(atr_percentile)
    if p < cfg.compression_pct:
        return "compression"
    if p <= cfg.normal_hi_pct:
        return "normal"
    if p <= cfg.expansion_hi_pct:
        return "expansion"
    return "hyper"


def portfolio_bucket_check(
    new_request_risk_pct: float,
    bucket_used_pct: float,
    bucket_cap_pct: float,
) -> Optional[str]:
    """
    Helper for portfolio bucket-cap enforcement (SPEC §C3).
    Returns None when the new request fits, else a human-readable reason.

      bucket_used_pct = sum of capital_at_risk_pct of all positions in this bucket
      bucket_cap_pct  = the cap (4.5 long / 3.0 short / 6.0 futures / 8.0 global)
    """
    projected = bucket_used_pct + new_request_risk_pct
    if projected > bucket_cap_pct:
        return (f"portfolio bucket would reach {projected:.2f}% > cap {bucket_cap_pct:.2f}% "
                f"(currently {bucket_used_pct:.2f}%, this trade {new_request_risk_pct:.2f}%)")
    return None
