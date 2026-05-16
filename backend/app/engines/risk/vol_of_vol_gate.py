"""
Sterling v4 — Vol-of-Vol Gate

The single-snapshot IVR misses regime *shifts*. By tracking the standard
deviation of IVR over a rolling window and the latest 24h Δ, we catch
post-FOMC IV crushes (high IVR snapshot but coming compression) and
expiry-week vol expansions (low IVR snapshot but coming pop).

Pure functions. No I/O. State is supplied by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class VolOfVolThresholds:
    """Tuneable thresholds. Defaults calibrated on BTC 2022–2024 monthly IVR."""
    std_threshold_pct_pts:    float = 12.0     # std of IVR > 12 pts → unstable
    delta_24h_threshold_pts:  float = 8.0      # |ΔIVR_24h| > 8 pts → spike
    min_samples:              int   = 14       # below this we abstain (no veto)


@dataclass(frozen=True)
class VolOfVolDecision:
    """Output. `block_naked=True` excludes naked premium (long *and* short).
    Spreads and futures still allowed."""
    block_naked: bool
    std_pct_pts: float
    delta_24h_pts: float
    reason: str


def compute(
    ivr_history: List[float],
    thresholds: Optional[VolOfVolThresholds] = None,
) -> VolOfVolDecision:
    """
    Args:
      ivr_history: chronological list of IVR readings (most recent last),
                   each in 0–100 scale.
      thresholds:  optional override; defaults to VolOfVolThresholds().

    Returns: a VolOfVolDecision.

    Behaviour:
      < min_samples observations → block_naked=False, reason="insufficient_data"
      std > std_threshold AND |Δ24h| > delta_threshold → block_naked=True
    """
    cfg = thresholds or VolOfVolThresholds()

    if len(ivr_history) < cfg.min_samples:
        return VolOfVolDecision(False, 0.0, 0.0, "insufficient_data")

    # Standard deviation over the full window
    n = len(ivr_history)
    mean = sum(ivr_history) / n
    var = sum((x - mean) ** 2 for x in ivr_history) / n
    std = var ** 0.5

    # 24h delta — last reading vs the one ~24h prior. We don't get explicit
    # timestamps so we use the second-to-last reading as proxy when granularity
    # is daily. Callers passing intra-day samples should subsample to daily.
    delta_24h = abs(ivr_history[-1] - ivr_history[-2])

    if std > cfg.std_threshold_pct_pts and delta_24h > cfg.delta_24h_threshold_pts:
        return VolOfVolDecision(
            block_naked=True,
            std_pct_pts=round(std, 2),
            delta_24h_pts=round(delta_24h, 2),
            reason=f"vol_of_vol_unstable: std={std:.1f}pts, Δ24h={delta_24h:.1f}pts",
        )

    return VolOfVolDecision(
        block_naked=False,
        std_pct_pts=round(std, 2),
        delta_24h_pts=round(delta_24h, 2),
        reason="stable",
    )
