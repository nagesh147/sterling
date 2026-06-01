"""Dynamic leverage for futures with fail-loud Kelly cold-start.

Pipeline:
  base_kelly  = Kelly fraction × win_rate × avg_R / risk_per_R    (fail closed)
  × circuit_breaker.size_multiplier()                              (CLEAR=1, WARN=0.5, HALT=0)
  × regime_adaptive_sizer.adapt(atr_percentile)                    (0.5 / 1.0 / 1.25 / 0.75)
  → leverage_pre_funding
  cap by funding_cost_gate.max_leverage_for_budget                 (hard rule)
  cap by profile.leverage_cap
  cap by exchange product max (BTC perp 100x, ETH 100x, ...)
  cap by mode.max_leverage_if_present                              (advisory)
  → final leverage

Cold-start (Plan-agent rule): when CalibrationService.win_rate() returns
None (< 10 closed trades), DO NOT silently fall back to a guessed value.
Cap leverage at 2× and emit warning so the FE shows "Cold start" banner.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.engines.derivatives.funding_cost_gate import FundingGateResult
from app.engines.derivatives.schemas import MarketContext, StrategyDerivativesProfile


COLD_START_LEVERAGE_CAP = 2.0
KELLY_FRACTION = 0.25                  # fractional Kelly — conservative
DEFAULT_RISK_PER_R = 0.02              # 2% per R as the "1 unit" denominator
EXCHANGE_PRODUCT_CAP = {
    "BTC": 100.0, "ETH": 100.0, "SOL": 50.0, "XRP": 25.0,
    "BNB": 50.0, "ADA": 25.0,
}


@dataclass
class LeverageDecision:
    leverage: float
    components: dict[str, float]
    warnings: list[str]


def _kelly_leverage(win_rate: Optional[float], avg_r: Optional[float]) -> tuple[float, list[str]]:
    """Returns (leverage_suggestion, warnings).

    Cold start (win_rate=None or sample too small): caller's responsibility
    to interpret 0.5% fixed as fail-safe; we return 2.0 max here so the
    upstream FE banner fires."""
    warnings: list[str] = []
    if win_rate is None or avg_r is None or win_rate <= 0 or avg_r <= 0:
        warnings.append("cold_start_kelly")
        return COLD_START_LEVERAGE_CAP, warnings

    # f* = p − (1−p)/b, where b = avg_R; b=R per dollar risked.
    f_star = win_rate - (1.0 - win_rate) / avg_r
    if f_star <= 0:
        # Negative-expectation regime — don't lever up
        warnings.append("kelly_negative_edge")
        return 1.0, warnings
    fractional = KELLY_FRACTION * f_star
    # Convert fractional Kelly (fraction of bankroll to put at risk) into
    # leverage by dividing by the per-trade risk fraction (default 2%).
    leverage = fractional / DEFAULT_RISK_PER_R
    return max(1.0, leverage), warnings


def decide(
    *,
    instrument_type: str,
    underlying: str,
    profile: StrategyDerivativesProfile,
    market: MarketContext,
    funding_result: FundingGateResult,
    requested_leverage: Optional[float] = None,
) -> LeverageDecision:
    """Run the full leverage pipeline. Options → leverage=1 by definition."""
    if instrument_type == "options":
        return LeverageDecision(
            leverage=1.0,
            components={"options": 1.0},
            warnings=[],
        )

    warnings: list[str] = []
    components: dict[str, float] = {}

    base_kelly, kelly_warns = _kelly_leverage(market.win_rate, market.avg_R)
    components["kelly_base"] = base_kelly
    warnings.extend(kelly_warns)

    # Use `is not None` rather than `or` — a CB HALT state sets size_mult=0.0,
    # which is falsy and the `or` fallback would silently treat HALT as CLEAR.
    cb_mult = float(market.cb_size_mult if market.cb_size_mult is not None else 1.0)
    components["cb_mult"] = cb_mult

    # Regime sizer — use the existing helper for consistency
    try:
        from app.engines.risk.regime_adaptive_sizer import adapt as _regime_adapt
        regime_mult = float(_regime_adapt(market.atr_percentile))
    except Exception:
        regime_mult = 1.0
    components["regime_mult"] = regime_mult

    lev_pre_funding = base_kelly * cb_mult * regime_mult
    components["pre_funding"] = lev_pre_funding

    # If a request came in (e.g. legacy callsite asked for X), use the
    # minimum of request and pre_funding so we never silently scale up.
    if requested_leverage is not None and requested_leverage > 0:
        lev_pre_funding = min(lev_pre_funding, requested_leverage)
        components["requested"] = requested_leverage

    # Funding cap
    if not funding_result.allowed and funding_result.max_leverage_for_budget > 0:
        if lev_pre_funding > funding_result.max_leverage_for_budget:
            warnings.append(f"funding_capped:{funding_result.reason}")
            lev_pre_funding = funding_result.max_leverage_for_budget
    components["after_funding"] = lev_pre_funding

    # Timeframe Adaptive Leverage Scaling
    # Short-term -> Higher leverage (20-50x effective). Longer holds -> Lower (5-15x).
    expected_hold = getattr(profile, "expected_hold_minutes", 60)
    timeframe_max_leverage = 50.0
    if expected_hold > 1440: # > 24h (Swing/Positional)
        timeframe_max_leverage = 15.0
    elif expected_hold > 240: # > 4h (Overnight)
        timeframe_max_leverage = 25.0

    # Profile cap
    lev_after_profile = min(lev_pre_funding, float(profile.leverage_cap), timeframe_max_leverage)
    components["after_profile"] = lev_after_profile

    # Exchange product cap
    product_cap = EXCHANGE_PRODUCT_CAP.get(underlying.upper(), 25.0)
    final = min(lev_after_profile, product_cap)
    if final < lev_after_profile:
        warnings.append(f"product_cap:{product_cap}x")
    components["product_cap"] = product_cap
    components["final"] = max(1.0, round(final, 2))

    return LeverageDecision(
        leverage=max(1.0, round(final, 2)),
        components=components,
        warnings=warnings,
    )
