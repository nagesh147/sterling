"""Pinning-risk gate for options inside the 2-day expiry window.

Near expiry, spot tends to pin at strikes carrying large open interest
("call walls" / "put walls"). A long option held into a pin loses
gamma+vega + may settle near intrinsic. Reuses the existing
scalping/delta_gamma wall detection.

Rule: when DTE ≤ 2 AND distance from spot to the nearest qualifying
strike (> 5% OI concentration) is < 1% of spot → veto. Plan-agent
flagged this as essential for late-week options.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.schemas.market import OptionSummary


@dataclass
class PinningResult:
    veto: bool
    nearest_pin_strike: Optional[float] = None
    pin_distance_pct: float = 0.0
    reason: str = ""


PIN_DTE_WINDOW = 2                  # only gate when DTE ≤ 2
PIN_DISTANCE_PCT = 0.015            # spot within 1.5% of a pinning strike
PIN_OI_CONCENTRATION_PCT = 0.20     # strike carries ≥ 20% of underlying's option OI


def check_pinning(
    candidate: OptionSummary,
    spot: float,
    full_chain: list[OptionSummary],
) -> PinningResult:
    """Veto when this candidate's underlying spot is within 1% of a
    pinning strike on a near-expiry chain.

    Pinning strikes are defined by OI concentration in either direction
    (calls + puts at the same strike combined). The candidate need not
    BE the pin — even an off-strike option is at risk because spot tends
    to gravitate to the pin until expiry.
    """
    if candidate.dte > PIN_DTE_WINDOW or spot <= 0 or not full_chain:
        return PinningResult(veto=False)

    # Aggregate OI per strike across calls + puts (only same-expiry contracts).
    same_expiry = [o for o in full_chain if o.expiry_date == candidate.expiry_date]
    if not same_expiry:
        return PinningResult(veto=False)
    total_oi = sum(o.open_interest for o in same_expiry)
    if total_oi <= 0:
        return PinningResult(veto=False)

    oi_by_strike: dict[float, float] = {}
    for o in same_expiry:
        oi_by_strike[o.strike] = oi_by_strike.get(o.strike, 0.0) + o.open_interest

    # Find the nearest strike with > PIN_OI_CONCENTRATION_PCT of total OI.
    pinning_strikes = [
        k for k, v in oi_by_strike.items()
        if v / total_oi >= PIN_OI_CONCENTRATION_PCT and v >= 50.0
    ]
    if not pinning_strikes:
        return PinningResult(veto=False)

    nearest = min(pinning_strikes, key=lambda s: abs(s - spot))

    # Calculate Max Pain (strike where max contracts expire worthless).
    # Since we are using OI as a proxy for pinning pressure, we'll check the Call/Put OI skew at the nearest pin.
    calls_oi = sum(o.open_interest for o in same_expiry if o.strike == nearest and o.option_type == "call")
    puts_oi = sum(o.open_interest for o in same_expiry if o.strike == nearest and o.option_type == "put")
    total_nearest_oi = calls_oi + puts_oi
    
    # Check GEX profile and Max Pain
    from app.engines.derivatives.gex_engine import calculate_gex_profile, calculate_max_pain
    gex_prof = calculate_gex_profile(same_expiry, spot)
    total_gex = gex_prof.get("total_gex", 0.0)
    call_wall = gex_prof.get("call_wall")
    
    # Max Pain Defense: If underlying is within 1.5% of Max Pain and <48h to expiry, veto.
    max_pain = calculate_max_pain(same_expiry)
    if max_pain > 0:
        pain_dist = abs(max_pain - spot) / spot
        if pain_dist < PIN_DISTANCE_PCT:
            return PinningResult(
                veto=True,
                nearest_pin_strike=max_pain,
                pin_distance_pct=pain_dist,
                reason=f"pin_risk:spot_near_max_pain_{int(max_pain)}@dist={pain_dist:.2%}",
            )
            
    if call_wall and abs(call_wall - spot) / spot < PIN_DISTANCE_PCT and total_gex > 50_000:
        return PinningResult(
            veto=True,
            nearest_pin_strike=call_wall,
            pin_distance_pct=abs(call_wall - spot) / spot,
            reason=f"pin_risk:spot_near_call_wall_{int(call_wall)}_high_gex",
        )
    
    skew = max(calls_oi, puts_oi) / total_nearest_oi if total_nearest_oi > 0 else 0.5
    
    distance_pct = abs(nearest - spot) / spot
    if distance_pct < PIN_DISTANCE_PCT:
        # Veto Rule: If underlying is within 1.5% of max pain and OI skew > 60/40, veto new long option entries
        if skew > 0.60:
            return PinningResult(
                veto=True,
                nearest_pin_strike=nearest,
                pin_distance_pct=distance_pct,
                reason=f"pin_risk:strike_{int(nearest)}@dist={distance_pct:.2%},skew={skew:.0%}>60%",
            )
        else:
            return PinningResult(
                veto=False, # We are near but skew is balanced, less dangerous max pain
                nearest_pin_strike=nearest,
                pin_distance_pct=distance_pct,
                reason=f"pin_warn:strike_{int(nearest)}@dist={distance_pct:.2%},skew={skew:.0%}<=60%",
            )
            
    return PinningResult(
        veto=False,
        nearest_pin_strike=nearest,
        pin_distance_pct=distance_pct,
    )
