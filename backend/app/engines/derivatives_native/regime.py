"""Volatility-regime engine for the native derivatives strategy.

Classifies the current vol regime from the live vol-risk-premium
(VRP = ATM IV / trailing realized vol) and, when enough real IV history has
accrued, an IV percentile. Until `iv_history` has >= MIN_IV_SAMPLES real
observations the IV-percentile is unavailable and the regime is flagged
`provisional` — vol-timing decisions built on it are hypotheses, not validated
edge (no historical IV existed at build time; the forward recorder accrues it).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# VRP thresholds (IV / realized-vol). Measured live 2026-06-02: BTC 0.91-1.18,
# ETH 0.90-1.21 — i.e. thin, mostly fair. Selling vol is only well-paid when rich.
VRP_CHEAP = 1.0     # IV below realized → buying is relatively cheap
VRP_RICH = 1.2      # IV well above realized → selling defined-risk vol is paid
MIN_IV_SAMPLES = 60  # distinct IV observations before the percentile is trusted
RICH_IVR = 70.0     # IV-rank above this = rich regime (gates the naked tier)


@dataclass
class RegimeState:
    vrp: Optional[float]
    iv_percentile: Optional[float]   # 0-100; None until enough history
    label: str                       # "cheap" | "fair" | "rich" | "unknown"
    provisional: bool                # True until >= MIN_IV_SAMPLES real IV obs
    reason: str


def compute_regime(
    *, atm_iv: Optional[float], realized_vol: Optional[float],
    underlying: str, iv_history: Optional[list[float]] = None,
) -> RegimeState:
    """Classify the vol regime. `iv_history` defaults to the DB series when None."""
    if iv_history is None:
        try:
            from app.services.db import get_iv_history
            iv_history = get_iv_history(underlying, limit=365)
        except Exception:
            iv_history = []

    vrp = (atm_iv / realized_vol) if (atm_iv and realized_vol and realized_vol > 0) else None

    iv_percentile: Optional[float] = None
    provisional = True
    if atm_iv and iv_history and len(iv_history) >= MIN_IV_SAMPLES:
        below = sum(1 for x in iv_history if x <= atm_iv)
        iv_percentile = round(100.0 * below / len(iv_history), 1)
        provisional = False

    if vrp is None:
        label = "unknown"
    elif vrp >= VRP_RICH:
        label = "rich"
    elif vrp < VRP_CHEAP:
        label = "cheap"
    else:
        label = "fair"

    reason = (
        f"vrp={vrp:.2f} ({label})" if vrp is not None else "vrp=n/a (no realized vol)"
    )
    if iv_percentile is not None:
        reason += f" · IVpct={iv_percentile:.0f}"
    elif label != "unknown":
        reason += " · IVpct provisional (insufficient history)"
    return RegimeState(vrp=vrp, iv_percentile=iv_percentile, label=label,
                       provisional=provisional, reason=reason)
