"""Gamma Exposure (GEX) engine for options routing and vetoes."""
from typing import Optional
from app.schemas.market import OptionSummary

def calculate_gex_profile(
    option_chain: list[OptionSummary], 
    underlying_price: float, 
    contract_size: float = 1.0
) -> dict[str, float]:
    """Calculates overall GEX and key strike levels.
    GEX ≈ Σ (Gamma_i × OI_i × Contract_Size × Underlying_Price)
    """
    total_gex = 0.0
    gex_by_strike = {}
    
    for opt in option_chain:
        if opt.open_interest <= 0 or opt.gamma <= 0:
            continue
            
        # Call GEX is positive, Put GEX is negative
        sign = 1.0 if opt.option_type == "call" else -1.0
        # GEX in USD per 1% move: GEX = Gamma × OI × Contract_Multiplier × (Underlying_Price²) × 0.01
        gex_val = sign * opt.gamma * opt.open_interest * contract_size * (underlying_price ** 2) * 0.01
        total_gex += gex_val
        gex_by_strike[opt.strike] = gex_by_strike.get(opt.strike, 0.0) + gex_val
        
    # Find zero gamma flip
    sorted_strikes = sorted(gex_by_strike.keys())
    cumulative_gex = 0.0
    zero_flip = underlying_price
    
    # Calculate cumulative GEX from lowest strike to highest to find where it flips
    prev_cumulative = 0.0
    for strike in sorted_strikes:
        gex = gex_by_strike[strike]
        cumulative_gex += gex
        if cumulative_gex >= 0 and prev_cumulative < 0:
            zero_flip = strike
            break
        prev_cumulative = cumulative_gex
            
    # Find call wall and put wall
    call_wall = max(gex_by_strike.items(), key=lambda x: x[1])[0] if gex_by_strike else underlying_price
    put_wall = min(gex_by_strike.items(), key=lambda x: x[1])[0] if gex_by_strike else underlying_price

    return {
        "total_gex": total_gex,
        "zero_gamma_flip": zero_flip,
        "call_wall": call_wall,
        "put_wall": put_wall,
    }

def calculate_max_pain(option_chain: list[OptionSummary]) -> float:
    """Max Pain — the settlement strike that minimizes total intrinsic payout
    to option holders (where the most open contracts expire worthless).

    For each candidate settlement price (each listed strike), sum the
    OI-weighted intrinsic value across every contract; the strike with the
    smallest total payout is Max Pain. Uses open_interest only — no premium
    field exists on OptionSummary (the prior version referenced a nonexistent
    `.premium` and crashed at runtime).
    """
    strikes = sorted({c.strike for c in option_chain})
    if not strikes:
        return 0.0

    best_strike = strikes[0]
    best_pain: float | None = None
    for settle in strikes:
        total_payout = 0.0
        for c in option_chain:
            if c.option_type == "call":
                intrinsic = max(0.0, settle - c.strike)
            else:
                intrinsic = max(0.0, c.strike - settle)
            total_payout += intrinsic * c.open_interest
        if best_pain is None or total_payout < best_pain:
            best_pain = total_payout
            best_strike = settle
    return best_strike

def get_gex_routing_influence(
    gex_profile: dict[str, float], 
    underlying_price: float
) -> float:
    """Returns an influence score from 0.0 to 100.0 for instrument chooser.
    High positive GEX -> mean reversion -> favors options.
    High negative GEX -> momentum -> favors futures.
    """
    total_gex = gex_profile.get("total_gex", 0.0)
    # We use an arbitrary scaling factor 100,000 for relative comparison.
    if total_gex > 100_000:
        return 100.0  # Strongly favors options
    elif total_gex < -100_000:
        return 0.0   # Strongly favors futures
        
    # Scale linearly between 0 and 100
    score = ((total_gex + 100_000) / 200_000) * 100.0
    return max(0.0, min(100.0, score))
