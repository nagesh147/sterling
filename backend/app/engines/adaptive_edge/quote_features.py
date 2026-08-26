"""Source-defined V2 quote feature operators.

Source: Adaptive Edge V2 A27 — Canonical Feature Set and Feature Semantics.
Only the mathematically complete, source-defined quote features are executable
here. Provider mapping, freshness, and market-data validity remain upstream.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class QuoteFeatures:
    mid: float
    spread: float
    spread_bps: float


def mid(*, bid: float, ask: float) -> float:
    """F-DER-MID: Mid = (Bid + Ask) / 2."""
    _require_finite_positive_prices(bid=bid, ask=ask)
    return (bid + ask) / 2.0


def spread(*, bid: float, ask: float) -> float:
    """F-DER-SPREAD: Spread = Ask - Bid."""
    _require_finite_positive_prices(bid=bid, ask=ask)
    return ask - bid


def spread_bps(*, bid: float, ask: float) -> float:
    """F-DER-SPREAD-BPS: 10000 * Spread / Mid, requiring Mid > 0."""
    m = mid(bid=bid, ask=ask)
    if m <= 0.0:
        raise ValueError("invalid quote: mid must be > 0 for spread-bps")
    return 10000.0 * (ask - bid) / m


def quote_features(*, bid: float, ask: float) -> QuoteFeatures:
    """Compute the complete source-defined derived quote feature set."""
    m = mid(bid=bid, ask=ask)
    s = ask - bid
    return QuoteFeatures(mid=m, spread=s, spread_bps=10000.0 * s / m)


def _require_finite_positive_prices(*, bid: float, ask: float) -> None:
    if not isfinite(bid) or not isfinite(ask):
        raise ValueError("bid and ask must be finite")
    if bid <= 0.0 or ask <= 0.0:
        raise ValueError("bid and ask must be > 0")
