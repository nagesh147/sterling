"""Liquidity composite for option contract ranking + hard floors.

Composite weights from the plan (Plan-agent's defensible defaults):
  0.5 × spread_score + 0.3 × OI score + 0.2 × volume_24h score.

Hard floors (any breach → contract drops out, regardless of composite):
  • spread_pct < profile.max_spread_pct
  • OI > profile.min_oi
  • volume_24h > profile.min_volume_24h_x_contract × contract_size

Returns a `LiquidityScore` whose `passes_floor` flag drives strike_picker
inclusion. The composite ranks the remaining survivors.
"""
from __future__ import annotations

from app.engines.derivatives.schemas import LiquidityScore, StrategyDerivativesProfile
from app.schemas.market import OptionSummary


CONTRACT_SIZE_USD = 1.0   # Delta India options multiplier = 1 USD per contract


def _spread_score(spread_pct: float, cap: float) -> float:
    """1.0 at 0% spread; linearly decays to 0.0 at the cap; 0 beyond."""
    if spread_pct <= 0:
        return 1.0
    if spread_pct >= cap:
        return 0.0
    return 1.0 - (spread_pct / cap)


def _oi_score(oi: float, floor: float) -> float:
    """Logarithmic — caps at 1.0 by 10× floor."""
    if oi <= floor:
        return 0.0
    import math
    return min(1.0, math.log10(oi / floor) / 1.0)


def _volume_score(vol_24h: float, floor_x_contract: float) -> float:
    floor = floor_x_contract * CONTRACT_SIZE_USD
    if vol_24h <= floor:
        return 0.0
    import math
    return min(1.0, math.log10(vol_24h / floor) / 1.0)


def score(opt: OptionSummary, profile: StrategyDerivativesProfile) -> LiquidityScore:
    """Compute the liquidity score for `opt`.

    Returns a LiquidityScore with `passes_floor=False` and a populated
    `floor_breach_reason` when any hard floor is violated; the composite
    is still reported (for diagnostics) but the candidate must be
    dropped before ranking."""
    spread_pct = float(opt.spread_pct or 0.0)
    if spread_pct == 0 and opt.ask > 0 and opt.bid > 0:
        spread_pct = (opt.ask - opt.bid) / max(opt.mid_price, 1e-9)

    oi = float(opt.open_interest or 0.0)
    vol = float(opt.volume_24h or 0.0)

    spread_s = _spread_score(spread_pct, profile.max_spread_pct)
    oi_s     = _oi_score(oi, profile.min_oi)
    vol_s    = _volume_score(vol, profile.min_volume_24h_x_contract)

    composite = 0.5 * spread_s + 0.3 * oi_s + 0.2 * vol_s

    # Hard floors
    if spread_pct > profile.max_spread_pct:
        return LiquidityScore(
            spread_score=spread_s, oi_score=oi_s, volume_score=vol_s,
            composite=composite, passes_floor=False,
            floor_breach_reason=f"spread {spread_pct:.2%} > {profile.max_spread_pct:.0%}",
        )
    if oi < profile.min_oi:
        return LiquidityScore(
            spread_score=spread_s, oi_score=oi_s, volume_score=vol_s,
            composite=composite, passes_floor=False,
            floor_breach_reason=f"oi {oi:.0f} < {profile.min_oi:.0f}",
        )
    if vol < profile.min_volume_24h_x_contract * CONTRACT_SIZE_USD:
        return LiquidityScore(
            spread_score=spread_s, oi_score=oi_s, volume_score=vol_s,
            composite=composite, passes_floor=False,
            floor_breach_reason=f"vol_24h {vol:.0f} < {profile.min_volume_24h_x_contract:.0f}×contract",
        )

    return LiquidityScore(
        spread_score=spread_s, oi_score=oi_s, volume_score=vol_s,
        composite=composite, passes_floor=True,
    )
