"""
Tiered market-impact model.
"""

SLIPPAGE_BPS = {
    (1,  "high"): 1,  (1,  "med"): 3,  (1,  "low"): 8,
    (5,  "high"): 2,  (5,  "med"): 5,  (5,  "low"): 15,
    (10, "high"): 5,  (10, "med"): 12, (10, "low"): 30,
    (25, "high"): 10, (25, "med"): 25, (25, "low"): 60,
    (50, "high"): 20, (50, "med"): 50, (50, "low"): 120,
}
OI_TIERS = {"high": 1000, "med": 200}


def slippage_bps(leverage: float, oi: float | None) -> float:
    lev_key = min([1, 5, 10, 25, 50], key=lambda k: abs(k - leverage))
    if oi is None:
        oi_key = "med"
    elif oi > OI_TIERS["high"]:
        oi_key = "high"
    elif oi > OI_TIERS["med"]:
        oi_key = "med"
    else:
        oi_key = "low"
    return float(SLIPPAGE_BPS[(lev_key, oi_key)])


def effective_entry(price: float, direction: int, leverage: float, oi: float | None) -> float:
    """Adjust entry price for slippage. direction: +1 long, -1 short."""
    bps = slippage_bps(leverage, oi)
    return price * (1 + direction * bps / 10_000)


def size_after_slippage(base_size: float, leverage: float, oi: float | None) -> float:
    """Reduce size proportionally to slippage cost."""
    bps = slippage_bps(leverage, oi)
    if bps <= 5:
        return base_size
    if bps <= 20:
        return base_size * 0.85
    if bps <= 50:
        return base_size * 0.65
    return base_size * 0.40
