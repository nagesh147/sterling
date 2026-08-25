"""Option strike and contract selection policy."""
from __future__ import annotations

from typing import Optional

# Standard strike intervals for common Indian F&O underlyings
DEFAULT_STRIKE_STEPS: dict[str, float] = {
    "ABB": 100.0,
    "RELIANCE": 20.0,
    "TATAMOTORS": 10.0,
    "INFY": 20.0,
    "HDFCBANK": 10.0,
    "ICICIBANK": 10.0,
    "SBIN": 10.0,
    "NIFTY 50": 50.0,
    "NIFTY BANK": 100.0,
    "NIFTY": 50.0,
    "BANKNIFTY": 100.0,
}


def get_strike_step(symbol: str, spot_price: float) -> float:
    """Determine strike step for an underlying."""
    clean = symbol.upper().replace("NSE:", "").strip()
    if clean in DEFAULT_STRIKE_STEPS:
        return DEFAULT_STRIKE_STEPS[clean]
    # Heuristic for unknown stocks based on spot price
    if spot_price > 5000:
        return 100.0
    if spot_price > 2000:
        return 50.0
    if spot_price > 1000:
        return 20.0
    if spot_price > 500:
        return 10.0
    return 5.0


def resolve_option_strike(
    symbol: str,
    spot_price: float,
    option_type: str,  # "CE" or "PE"
    policy: str = "OTM1",  # "ATM", "OTM1", "OTM2"
    step: Optional[float] = None,
) -> float:
    """Resolve the target strike based on moneyness policy.

    In the TradeAlphaGuru framework, high-momentum breakout trades frequently buy
    OTM1/OTM2 strikes for aggressive gamma expansion and Multi-X returns.
    """
    strike_step = step or get_strike_step(symbol, spot_price)
    atm_strike = int(spot_price / strike_step + 0.5) * strike_step

    if policy == "ATM":
        return float(atm_strike)

    if option_type == "CE":
        if policy == "OTM1":
            return float(atm_strike + strike_step)
        elif policy == "OTM2":
            return float(atm_strike + (2.0 * strike_step))
        return float(atm_strike + strike_step)
    else:  # "PE"
        if policy == "OTM1":
            return float(atm_strike - strike_step)
        elif policy == "OTM2":
            return float(atm_strike - (2.0 * strike_step))
        return float(atm_strike - strike_step)
