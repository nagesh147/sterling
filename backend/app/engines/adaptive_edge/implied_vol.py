"""Implied volatility from a live option quote.

Every short-volatility conclusion in this engine's research depended on an
assumed implied-to-realised ratio, because no store here holds option price
history — not the local SQLite, not the pendrive lake. That assumption is the
single largest unknown in the strategy and it was never measurable offline.

It is measurable at runtime. The engine has quoted premiums. This module turns
them into an implied volatility, so the comparison the strategy rests on stops
being an assumption and becomes a reading.

The inversion uses the at-the-money approximation `straddle ~= 0.7979 * sigma *
sqrt(T) * S`, which is accurate to well under a percent for near-the-money
options and does not need an iterative solve. Away from the money it degrades,
which is why `atm_implied_vol` refuses a strike that is not close to spot rather
than returning a number that looks fine.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

#: Black-Scholes at the money: a straddle is worth about this times
#: `sigma * sqrt(T) * S`. Exactly `sqrt(2/pi)`.
ATM_STRADDLE_COEFFICIENT = 0.7979

#: Trading minutes in a year on NSE: 375 a session, 250 sessions.
MINUTES_PER_YEAR = 375 * 250

#: How far from spot a strike may sit and still be treated as at the money. The
#: approximation above is what degrades, so this is the boundary of the model
#: rather than a preference.
MAX_MONEYNESS_DRIFT = 0.01


@dataclass(frozen=True)
class ImpliedReading:
    """What the market is charging, beside what the tape has been doing.

    `ratio` is the number the strategy turns on. Above 1 the market charges more
    movement than has been realised — the variance risk premium, and the reason
    buying volatility loses. Below 1 the opposite.
    """

    implied_vol: float
    realised_vol: float
    ratio: float
    straddle_bps: float
    minutes_to_expiry: float
    strike: float
    spot: float

    @property
    def premium_rich(self) -> bool:
        return self.ratio > 1.0


def annualise_minute_vol(vol_bps_per_minute: float) -> float:
    """A per-minute standard deviation in basis points to an annual fraction.

    Both sides of the comparison have to be in the same units, and getting this
    wrong scales the ratio by about 306 — which would not look like an error,
    it would look like a spectacular edge.
    """
    return (vol_bps_per_minute / 10_000.0) * math.sqrt(MINUTES_PER_YEAR)


def atm_implied_vol(
    *,
    call_premium: float,
    put_premium: float,
    spot: float,
    strike: float,
    minutes_to_expiry: float,
) -> Optional[float]:
    """Annualised implied volatility from a quoted at-the-money straddle.

    Returns None rather than a number when the inputs cannot support one: an
    unpriced leg, an expired contract, or a strike far enough from spot that the
    at-the-money approximation no longer holds. A silent wrong answer here
    propagates into every sizing decision downstream.
    """
    if call_premium <= 0 or put_premium <= 0 or spot <= 0 or minutes_to_expiry <= 0:
        return None
    if strike > 0 and abs(strike - spot) / spot > MAX_MONEYNESS_DRIFT:
        # Not at the money. The approximation is only good near it, and a strike
        # 5% away would quote a premium this formula reads as low volatility.
        return None

    years = minutes_to_expiry / MINUTES_PER_YEAR
    straddle_fraction = (call_premium + put_premium) / spot
    denominator = ATM_STRADDLE_COEFFICIENT * math.sqrt(years)
    if denominator <= 0:
        return None
    return straddle_fraction / denominator


def read(
    *,
    call_premium: float,
    put_premium: float,
    spot: float,
    strike: float,
    minutes_to_expiry: float,
    realised_vol_bps_per_minute: float,
) -> Optional[ImpliedReading]:
    """The live implied-to-realised reading, or None if it cannot be taken."""
    implied = atm_implied_vol(
        call_premium=call_premium, put_premium=put_premium, spot=spot,
        strike=strike, minutes_to_expiry=minutes_to_expiry)
    if implied is None:
        return None
    realised = annualise_minute_vol(realised_vol_bps_per_minute)
    if realised <= 0:
        return None
    return ImpliedReading(
        implied_vol=implied,
        realised_vol=realised,
        ratio=implied / realised,
        straddle_bps=((call_premium + put_premium) / spot) * 10_000.0,
        minutes_to_expiry=minutes_to_expiry,
        strike=strike,
        spot=spot,
    )
