"""
Sterling v4 — Kelly-based ruin probability calculator.

P(ruin) ≈ exp(-2 * br * edge / variance)

where:
  br     = bankroll fraction risked per trade
  edge   = win_rate * avg_win - (1 - win_rate) * avg_loss
  variance ≈ win_rate * avg_win^2 + (1 - win_rate) * avg_loss^2

When edge <= 0, ruin is guaranteed → return 1.0.
When variance is 0 (no trades), return 0.0.

The finite-horizon correction applies the infinite-horizon ruin probability
across n trades: P(ruin_n) ≈ 1 - (1 - P(ruin_infinity))^n.
"""
from __future__ import annotations
import math
from typing import Optional

RUIN_PROB_MAX = 0.05  # Maximum acceptable ruin probability (5%)


def ruin_probability(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    bankroll_fraction: float = 0.01,
    n_trades: Optional[int] = None,
) -> float:
    """
    Compute approximate ruin probability under Kelly sizing.

    Args:
        win_rate: probability of a winning trade (0.0 to 1.0)
        avg_win: average return when winning (positive fraction, e.g. 0.02 = 2%)
        avg_loss: average return when losing (positive fraction, e.g. 0.01 = 1%)
        bankroll_fraction: fraction of bankroll risked per trade (default 1%)
        n_trades: number of trades for finite-horizon correction. If None,
                  returns infinite-horizon probability.

    Returns:
        float between 0.0 and 1.0 representing probability of ruin.
    """
    if avg_loss <= 0 or avg_win <= 0:
        return 1.0  # undefined edge → guaranteed ruin

    edge = win_rate * avg_win - (1.0 - win_rate) * avg_loss
    if edge <= 0:
        return 1.0  # negative edge → guaranteed ruin

    variance = win_rate * (avg_win ** 2) + (1.0 - win_rate) * (avg_loss ** 2)
    if variance <= 0:
        return 0.0

    # Infinite-horizon ruin probability.
    # Clamp exponent to prevent underflow (exp(-50) ≈ 0).
    exponent = -2.0 * bankroll_fraction * edge / variance
    p_ruin = math.exp(max(-50.0, min(0.0, exponent)))

    # Finite-horizon correction: after n trades, ruin = 1 - (1 - p_infinity)^n
    if n_trades is not None and n_trades > 0:
        p_ruin = 1.0 - (1.0 - p_ruin) ** n_trades

    return round(p_ruin, 6)


def size_with_ruin_limit(
    target_risk_pct: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    n_trades_estimate: int = 100,
    ruin_max: float = RUIN_PROB_MAX,
) -> float:
    """
    Adjust target_risk_pct downward until ruin probability <= ruin_max.

    Uses binary search (10 iterations) to find the smallest risk fraction
    that satisfies the ruin constraint. Falls back to target_risk_pct * 0.01
    as a hard floor if the constraint cannot be met.

    Args:
        target_risk_pct: original Kelly-derived risk percentage
        win_rate: winning probability
        avg_win: average win fraction
        avg_loss: average loss fraction
        n_trades_estimate: expected trade count for finite-horizon correction
        ruin_max: maximum acceptable ruin probability (default 5%)

    Returns:
        Adjusted risk percentage that satisfies the ruin constraint.
    """
    current_risk = target_risk_pct
    for _ in range(10):
        p_ruin = ruin_probability(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            bankroll_fraction=current_risk,
            n_trades=n_trades_estimate,
        )
        if p_ruin <= ruin_max:
            return current_risk
        # Reduce risk by 20% and re-check
        current_risk *= 0.8
        # Hard floor: never go below 1% of original target
        floor = target_risk_pct * 0.01
        if current_risk < floor:
            return floor
    return current_risk