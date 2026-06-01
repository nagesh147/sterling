"""Liquidity composite for option contract ranking + hard floors.

Composite weights from the plan (Plan-agent's defensible defaults):
  0.6 × spread_score + 0.4 × OI/volume score.

Hard floors (any breach → contract drops out, regardless of composite):
  • spread_pct < max_acceptable_spread (Adaptive based on timeframe)
  • OI > min_oi (Adaptive based on timeframe)
  • volume_24h > min_volume
"""
from __future__ import annotations

from app.engines.derivatives.schemas import LiquidityScore, StrategyDerivativesProfile
from app.schemas.market import OptionSummary


CONTRACT_SIZE_USD = 1.0   # Delta India options multiplier = 1 USD per contract


def score(opt: OptionSummary, profile: StrategyDerivativesProfile, expected_hold_days: float = 0.0) -> LiquidityScore:
    spread_pct = float(opt.spread_pct or 0.0)
    if spread_pct == 0 and opt.ask > 0 and opt.bid > 0:
        spread_pct = (opt.ask - opt.bid) / max(opt.mid_price, 1e-9)

    oi = float(opt.open_interest or 0.0)
    vol = float(opt.volume_24h or 0.0)

    # Timeframe Adaptive Thresholds
    is_scalping = expected_hold_days < 1.0 # Includes scalping/intraday/overnight
    
    max_acceptable_spread = 0.08 if is_scalping else 0.15
    immediate_veto_spread = 0.15 if is_scalping else 0.18
    min_oi_threshold = 150.0 if is_scalping else 50.0
    min_volume_threshold = 30.0

    # Spread Score (0-1)
    spread_score = max(0.0, 1.0 - (spread_pct / max_acceptable_spread))
    
    # Liquidity Score (Volume + OI)
    norm_volume = min(1.0, vol / min_volume_threshold)
    norm_oi = min(1.0, oi / min_oi_threshold)
    liq_score = 0.55 * norm_volume + 0.45 * norm_oi
    
    composite = 0.6 * spread_score + 0.4 * liq_score

    # Hard floors / Immediate Veto
    if spread_pct > immediate_veto_spread:
        return LiquidityScore(
            spread_score=spread_score, oi_score=norm_oi, volume_score=norm_volume,
            composite=composite, passes_floor=False,
            floor_breach_reason=f"spread {spread_pct:.2%} > veto {immediate_veto_spread:.0%}",
        )
    if oi < 50.0: # Strong Penalty / Veto
        return LiquidityScore(
            spread_score=spread_score, oi_score=norm_oi, volume_score=norm_volume,
            composite=composite, passes_floor=False,
            floor_breach_reason=f"oi {oi:.0f} < strong_penalty 50",
        )
    if vol < 30.0 * CONTRACT_SIZE_USD:
        return LiquidityScore(
            spread_score=spread_score, oi_score=norm_oi, volume_score=norm_volume,
            composite=composite, passes_floor=False,
            floor_breach_reason=f"vol {vol:.0f} < strong_penalty 30",
        )
        
    # Timeframe specific adaptive veto
    if spread_pct > max_acceptable_spread:
        return LiquidityScore(
            spread_score=spread_score, oi_score=norm_oi, volume_score=norm_volume,
            composite=composite, passes_floor=False,
            floor_breach_reason=f"spread {spread_pct:.2%} > tf_adaptive {max_acceptable_spread:.0%}",
        )
    if oi < min_oi_threshold:
        return LiquidityScore(
            spread_score=spread_score, oi_score=norm_oi, volume_score=norm_volume,
            composite=composite, passes_floor=False,
            floor_breach_reason=f"oi {oi:.0f} < tf_adaptive {min_oi_threshold:.0f}",
        )

    return LiquidityScore(
        spread_score=spread_score, oi_score=norm_oi, volume_score=norm_volume,
        composite=composite, passes_floor=True,
    )
