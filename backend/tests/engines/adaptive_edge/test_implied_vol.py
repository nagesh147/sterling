"""Implied volatility from live quotes.

This is the number every short-volatility conclusion in the research depended on
and none of them could measure, because no store here holds option prices. It is
measurable at runtime, which is the point of this module — so the tests are
mostly about refusing to produce a number that would be wrong.
"""
from __future__ import annotations

import math

import pytest

from app.engines.adaptive_edge.implied_vol import (
    MAX_MONEYNESS_DRIFT,
    MINUTES_PER_YEAR,
    annualise_minute_vol,
    atm_implied_vol,
    read,
)

SPOT = 24_800.0
THREE_DAYS = 3 * 375


def _iv(call=95.0, put=90.0, spot=SPOT, strike=SPOT, minutes=THREE_DAYS):
    return atm_implied_vol(call_premium=call, put_premium=put, spot=spot,
                           strike=strike, minutes_to_expiry=minutes)


# ----------------------------------------------------------- the inversion

def test_a_dearer_straddle_implies_more_volatility():
    assert _iv(call=140, put=135) > _iv(call=95, put=90)


def test_more_time_to_expiry_implies_less_volatility_for_the_same_premium():
    """The same rupees spread over more days is a lower rate."""
    assert _iv(minutes=7 * 375) < _iv(minutes=1 * 375)


def test_the_inversion_round_trips():
    """Price a straddle from a known volatility, read it back."""
    iv, years = 0.14, THREE_DAYS / MINUTES_PER_YEAR
    straddle = 0.7979 * iv * math.sqrt(years) * SPOT
    recovered = _iv(call=straddle / 2, put=straddle / 2)
    assert recovered == pytest.approx(iv, rel=1e-6)


# ------------------------------------------------------- refusing to guess

def test_an_unpriced_leg_gives_no_reading():
    assert _iv(call=0.0) is None
    assert _iv(put=0.0) is None


def test_an_expired_contract_gives_no_reading():
    assert _iv(minutes=0) is None
    assert _iv(minutes=-10) is None


def test_a_strike_away_from_the_money_is_refused():
    """The approximation only holds near the money. A far strike quotes a small
    premium this formula would read as low volatility, which is backwards."""
    assert _iv(strike=SPOT * (1 + MAX_MONEYNESS_DRIFT * 3)) is None
    assert _iv(strike=SPOT * (1 - MAX_MONEYNESS_DRIFT * 3)) is None


def test_a_strike_just_inside_the_band_is_accepted():
    assert _iv(strike=SPOT * (1 + MAX_MONEYNESS_DRIFT * 0.5)) is not None


# -------------------------------------------------------------- annualising

def test_annualising_uses_trading_minutes_not_calendar():
    """Both sides of the ratio must be in the same units. Getting this wrong
    scales it by about 306, which would not look like a bug — it would look
    like a spectacular edge."""
    assert annualise_minute_vol(3.0) == pytest.approx((3.0 / 10_000) * math.sqrt(MINUTES_PER_YEAR))
    assert 0.05 < annualise_minute_vol(3.0) < 0.15


# ------------------------------------------------------------- the reading

def test_the_ratio_is_implied_over_realised():
    r = read(call_premium=95, put_premium=90, spot=SPOT, strike=SPOT,
             minutes_to_expiry=THREE_DAYS, realised_vol_bps_per_minute=3.0)
    assert r.ratio == pytest.approx(r.implied_vol / r.realised_vol)


def test_a_rich_premium_is_flagged():
    """Above 1 the market charges more movement than has been realised — the
    variance risk premium, and the reason buying volatility loses."""
    rich = read(call_premium=200, put_premium=195, spot=SPOT, strike=SPOT,
                minutes_to_expiry=THREE_DAYS, realised_vol_bps_per_minute=3.0)
    cheap = read(call_premium=30, put_premium=28, spot=SPOT, strike=SPOT,
                 minutes_to_expiry=THREE_DAYS, realised_vol_bps_per_minute=3.0)
    assert rich.premium_rich is True
    assert cheap.premium_rich is False


def test_no_realised_volatility_gives_no_reading():
    assert read(call_premium=95, put_premium=90, spot=SPOT, strike=SPOT,
                minutes_to_expiry=THREE_DAYS, realised_vol_bps_per_minute=0.0) is None
