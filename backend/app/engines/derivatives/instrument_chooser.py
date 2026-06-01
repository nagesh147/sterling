"""Options-vs-futures decision for the central DerivativesSelector.

Improved Mathematical Routing Logic:
Use a composite routing score (0–100). Route to Options if score > 55; else Futures.

Formula Example:
routing_score = (
    0.30 * vol_regime_score +
    0.25 * timeframe_factor +
    0.20 * conviction_score +
    0.15 * liquidity_penalty +
    0.10 * greeks_advantage
)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.engines.derivatives.schemas import (
    InstrumentBias, MarketContext, SignalContext, StrategyDerivativesProfile,
)


@dataclass
class InstrumentDecision:
    instrument_type: str            # "futures" | "options"
    reason: str
    breakdown: dict[str, float]


def choose(
    *,
    signal: SignalContext,
    profile: StrategyDerivativesProfile,
    market: MarketContext,
    best_option_expected_r: Optional[float],
    best_option_spread: Optional[float] = None,
    best_option_gamma: Optional[float] = None,
    front_month_iv: Optional[float] = None,
    back_month_iv: Optional[float] = None,
    gex_influence_score: float = 50.0,
) -> InstrumentDecision:
    breakdown: dict[str, float] = {
        "signal_score": signal.signal_score,
        "best_option_R": best_option_expected_r or 0.0,
        "ivr_pct": market.ivr_pct or 0.0,
        "basis_pct": market.basis_pct or 0.0,
    }

    # Hard overrides
    if profile.instrument_bias == InstrumentBias.FUTURES:
        return InstrumentDecision("futures", "profile=FUTURES", breakdown)
    if profile.instrument_bias == InstrumentBias.OPTIONS:
        return InstrumentDecision("options", "profile=OPTIONS", breakdown)

    # ── Hard Vetoes ────────────────────────────────────────────────────────
    # Veto 1: Option bid-ask spread > 12%
    if best_option_spread is not None and best_option_spread > 0.12:
        return InstrumentDecision("futures", f"hard_veto:spread_{best_option_spread:.1%}>12%", breakdown)
    
    # Veto 2: Front-month IV diff too high
    if front_month_iv is not None and back_month_iv is not None:
        front_back_diff = front_month_iv - back_month_iv
        if front_back_diff > profile.front_back_iv_diff_max:
             return InstrumentDecision("futures", "hard_veto:front_back_iv_diff_too_high", breakdown)

    # Veto 3: IVR Cap limit breached
    if market.ivr_pct is not None and market.ivr_pct > profile.ivr_pct_naked_max:
        return InstrumentDecision("futures", f"hard_veto:ivr_too_high:{market.ivr_pct:.0f}>{profile.ivr_pct_naked_max}", breakdown)

    # ── Composite Mathematical Routing Logic ───────────────────────────────
    
    # 1. Volatility Regime (30%): High IVR (>60) → 100, Low IVR (<30) → 0
    vol_regime_score = 0.0
    if market.ivr_pct is not None:
        if market.ivr_pct > 60:
            vol_regime_score = 100.0
        elif market.ivr_pct < 30:
            vol_regime_score = 0.0
        else:
            vol_regime_score = ((market.ivr_pct - 30) / 30) * 100

    # 2. Time Horizon (25%): Scalping/Intraday → Futures (0). Overnight+ → Options (100).
    timeframe_factor = 0.0
    expected_hold = getattr(profile, "expected_hold_minutes", 60)
    if expected_hold > 1440: # > 24h
        timeframe_factor = 100.0
    elif expected_hold > 240: # > 4h
        timeframe_factor = 50.0

    # 3. Conviction & Edge (20%): 
    # Strong directional signal with technical confirmation → Futures. Asymmetric payoff needed → Options.
    # We use best_option_expected_r as the asymmetry measure.
    conviction_score = 50.0
    if best_option_expected_r is not None and best_option_expected_r >= 3.0:
        conviction_score = 100.0 # High asymmetry favours Options
    elif signal.signal_score >= 80:
        conviction_score = 0.0 # High conviction favours Futures

    # 4. Liquidity & Cost (15%):
    # Wider option spreads or low OI → Futures.
    liquidity_penalty = 100.0
    if best_option_spread is not None:
        # Spread 0% -> 100, Spread 12% -> 0
        liquidity_penalty = max(0.0, 100.0 - (best_option_spread / 0.12 * 100.0))

    # 5. Greeks Alignment (10%): High gamma/vega desired → Options.
    greeks_advantage = 50.0
    if best_option_gamma is not None:
        if best_option_gamma > 0.0005:
            greeks_advantage = 100.0
        elif best_option_gamma < 0.0001:
            greeks_advantage = 0.0

    routing_score = (
        0.25 * vol_regime_score +
        0.20 * timeframe_factor +
        0.20 * conviction_score +
        0.15 * gex_influence_score +
        0.10 * liquidity_penalty +
        0.10 * greeks_advantage
    )

    breakdown["routing_score"] = routing_score
    breakdown["vol_regime"] = vol_regime_score
    breakdown["timeframe"] = timeframe_factor
    breakdown["conviction"] = conviction_score
    breakdown["gex_influence"] = gex_influence_score
    breakdown["liquidity"] = liquidity_penalty
    breakdown["greeks"] = greeks_advantage

    # Basis check override logic
    basis = market.basis_pct or 0.0
    if signal.direction == "long" and basis > 0.005:
        # High positive basis means futures bleed via funding, push towards options
        routing_score += 15.0
        breakdown["basis_high_bonus"] = 15.0
    elif signal.direction == "short" and basis < -0.005:
        # Negative basis → futures shorts get paid funding, pull towards futures
        routing_score -= 15.0
        breakdown["funding_pays_shorts_penalty"] = 15.0

    if routing_score > 55.0:
        return InstrumentDecision("options", f"score_routing:{routing_score:.1f}>55", breakdown)

    return InstrumentDecision("futures", f"score_routing:{routing_score:.1f}<=55", breakdown)
