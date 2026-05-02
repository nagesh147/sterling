"""
Black-Scholes analytical pricing for backtest option estimation.

All functions are pure/deterministic — no I/O.
Used to compute theoretical ATM option P&L alongside candle-based signal replay.
"""
import math
from typing import Optional


def _norm_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(spot: float, strike: float, dte: int, iv: float, r: float = 0.0):
    T = dte / 365.0
    if T <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return None, None
    sqrtT = math.sqrt(T)
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * T) / (iv * sqrtT)
    d2 = d1 - iv * sqrtT
    return d1, d2


def bs_price(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    option_type: str,   # "call" | "put"
    r: float = 0.0,
) -> Optional[float]:
    """Black-Scholes theoretical option price. Returns None on bad inputs."""
    d1, d2 = _d1_d2(spot, strike, dte, iv, r)
    if d1 is None:
        return None
    T = dte / 365.0
    df = math.exp(-r * T)
    if option_type == "call":
        price = spot * _norm_cdf(d1) - strike * df * _norm_cdf(d2)
    else:
        price = strike * df * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
    return round(max(0.0, price), 6)


def bs_delta(spot: float, strike: float, dte: int, iv: float, option_type: str) -> float:
    d1, _ = _d1_d2(spot, strike, dte, iv)
    if d1 is None:
        return 0.0
    raw = _norm_cdf(d1)
    return round(raw if option_type == "call" else raw - 1.0, 4)


def bs_gamma(spot: float, strike: float, dte: int, iv: float) -> float:
    d1, _ = _d1_d2(spot, strike, dte, iv)
    if d1 is None:
        return 0.0
    T = dte / 365.0
    return round(_norm_pdf(d1) / (spot * iv * math.sqrt(T)), 6)


def bs_vega(spot: float, strike: float, dte: int, iv: float) -> float:
    """Vega per 1% IV move (divided by 100 from standard formula)."""
    d1, _ = _d1_d2(spot, strike, dte, iv)
    if d1 is None:
        return 0.0
    T = dte / 365.0
    return round(spot * _norm_pdf(d1) * math.sqrt(T) / 100.0, 6)


def bs_theta(
    spot: float, strike: float, dte: int, iv: float, option_type: str, r: float = 0.0
) -> float:
    """Theta per calendar day (negative = time decay)."""
    d1, d2 = _d1_d2(spot, strike, dte, iv, r)
    if d1 is None:
        return 0.0
    T = dte / 365.0
    df = math.exp(-r * T)
    term1 = -(spot * _norm_pdf(d1) * iv) / (2.0 * math.sqrt(T))
    if option_type == "call":
        term2 = -r * strike * df * _norm_cdf(d2)
    else:
        term2 = r * strike * df * _norm_cdf(-d2)
    return round((term1 + term2) / 365.0, 6)


def atm_option_pnl_pct(
    spot_entry: float,
    spot_exit: float,
    dte_entry: int,
    dte_exit: int,
    iv: float,
    option_type: str,
) -> Optional[float]:
    """
    Theoretical P&L as a % of entry premium for an ATM option.
    Uses the entry spot as the strike (at-the-money at entry).
    Returns None if entry premium is zero/invalid.
    """
    strike = spot_entry
    entry = bs_price(spot_entry, strike, dte_entry, iv, option_type)
    if not entry or entry <= 1e-8:
        return None
    exit_p = bs_price(spot_exit, strike, max(0, dte_exit), iv, option_type) or 0.0
    return round((exit_p - entry) / entry * 100.0, 2)
