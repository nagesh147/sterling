"""Option delta recovered from the market, not assumed.

Kite publishes no Greeks, so the ORB trade plan previously assumed a delta of
0.50 for every contract. Everything in the premium domain is derived from that
number -- the stop premium armed at the broker included -- so for a 0.25-delta
OTM contract the modelled stop sat roughly twice as far out as intended.

Nothing here invents a price. The premium is an observable; implied volatility
is solved from it by bisection on the Black-Scholes price, and delta follows
from that volatility. When the premium cannot support a solution the caller is
told so and falls back explicitly rather than silently.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from math import erf, exp, isfinite, log, sqrt
from typing import Literal
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
OptionType = Literal["CE", "PE"]

#: Indian index and stock options stop trading at 15:30 IST on expiry day.
EXPIRY_TIME_IST = (15, 30)

#: Never divide by a zero horizon: one minute is the smallest meaningful step.
_MIN_YEARS = 1.0 / (365.0 * 24.0 * 60.0)

_VOL_FLOOR = 1e-4
_VOL_CEILING = 6.0          # 600% covers expiry-day index options
_TOLERANCE = 1e-6
_MAX_ITERATIONS = 100


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def years_to_expiry(expiry: date, now: datetime) -> float:
    """Time to the 15:30 IST expiry cutoff, in years. Floored, never negative."""
    cutoff = datetime.combine(expiry, datetime.min.time(), tzinfo=IST) + timedelta(
        hours=EXPIRY_TIME_IST[0], minutes=EXPIRY_TIME_IST[1]
    )
    reference = now if now.tzinfo else now.replace(tzinfo=IST)
    seconds = (cutoff - reference.astimezone(IST)).total_seconds()
    return max(_MIN_YEARS, seconds / (365.0 * 24.0 * 60.0 * 60.0))


def black_scholes_price(spot: float, strike: float, years: float, vol: float, rate: float, option_type: OptionType) -> float:
    if years <= 0 or vol <= 0:
        return max(spot - strike, 0.0) if option_type == "CE" else max(strike - spot, 0.0)
    root = vol * sqrt(years)
    d1 = (log(spot / strike) + (rate + 0.5 * vol * vol) * years) / root
    d2 = d1 - root
    discounted = strike * exp(-rate * years)
    if option_type == "CE":
        return spot * _normal_cdf(d1) - discounted * _normal_cdf(d2)
    return discounted * _normal_cdf(-d2) - spot * _normal_cdf(-d1)


def black_scholes_delta(spot: float, strike: float, years: float, vol: float, rate: float, option_type: OptionType) -> float:
    """Delta. At expiry it is the step function, which is the correct limit."""
    if years <= 0 or vol <= 0:
        if option_type == "CE":
            return 1.0 if spot > strike else 0.0
        return -1.0 if spot < strike else 0.0
    d1 = (log(spot / strike) + (rate + 0.5 * vol * vol) * years) / (vol * sqrt(years))
    return _normal_cdf(d1) if option_type == "CE" else _normal_cdf(d1) - 1.0


def implied_volatility(
    premium: float, spot: float, strike: float, years: float, rate: float, option_type: OptionType
) -> float | None:
    """Solve for volatility by bisection, or return None if the premium cannot.

    Bisection rather than Newton-Raphson: the price is monotone in volatility, so
    bisection cannot diverge, and a bracket that fails to contain the premium is
    a definitive "this quote is not consistent with the model" rather than a
    silently wrong root.
    """
    if not all(isfinite(x) for x in (premium, spot, strike, years, rate)):
        return None
    if premium <= 0 or spot <= 0 or strike <= 0 or years <= 0:
        return None

    intrinsic = max(spot - strike, 0.0) if option_type == "CE" else max(strike - spot, 0.0)
    if premium < intrinsic - _TOLERANCE:
        return None                      # below intrinsic: arbitrage or a bad quote
    if premium > black_scholes_price(spot, strike, years, _VOL_CEILING, rate, option_type):
        return None                      # richer than 600% vol explains

    low, high = _VOL_FLOOR, _VOL_CEILING
    for _ in range(_MAX_ITERATIONS):
        mid = 0.5 * (low + high)
        price = black_scholes_price(spot, strike, years, mid, rate, option_type)
        if abs(price - premium) < _TOLERANCE:
            return mid
        if price < premium:
            low = mid
        else:
            high = mid
    settled = 0.5 * (low + high)
    # Accept only a solution that actually reprices the observed premium.
    if abs(black_scholes_price(spot, strike, years, settled, rate, option_type) - premium) > max(0.01, 0.001 * premium):
        return None
    return settled


def implied_delta(
    premium: float,
    spot: float,
    strike: float,
    expiry: date,
    option_type: OptionType,
    *,
    now: datetime,
    rate: float,
) -> float | None:
    """Delta implied by the traded premium, or None when it cannot be recovered."""
    years = years_to_expiry(expiry, now)
    vol = implied_volatility(premium, spot, strike, years, rate, option_type)
    if vol is None:
        return None
    delta = black_scholes_delta(spot, strike, years, vol, rate, option_type)
    return delta if isfinite(delta) else None
