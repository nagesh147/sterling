"""Delta recovered from the traded premium instead of assumed.

Kite publishes no Greeks, so the plan used to assume delta 0.50 for every
contract -- and `stop_premium`, the number armed at the broker, is derived from
it. These tests pin the Black-Scholes implementation against textbook values,
then pin the fallback behaviour, because a wrong delta is worse than an admitted
assumption.
"""
from datetime import date, datetime, timedelta, timezone
from math import exp

import pytest

from app.engines.nifty_orb_greeks import (
    black_scholes_delta,
    black_scholes_price,
    implied_delta,
    implied_volatility,
    years_to_expiry,
)
from app.engines.nifty_orb_options import OptionContract, Signal, StrategyConfig, build_trade_plan

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 8, 21, 10, 30, tzinfo=IST)
EXPIRY = date(2026, 8, 27)


# --------------------------------------------------------------------------
# the model, against published values
# --------------------------------------------------------------------------

def test_price_matches_the_textbook_case():
    # S=100 K=100 t=1 vol=20% r=5%
    assert black_scholes_price(100, 100, 1, 0.20, 0.05, "CE") == pytest.approx(10.4506, abs=1e-4)
    assert black_scholes_price(100, 100, 1, 0.20, 0.05, "PE") == pytest.approx(5.5735, abs=1e-4)


def test_delta_matches_the_textbook_case():
    assert black_scholes_delta(100, 100, 1, 0.20, 0.05, "CE") == pytest.approx(0.6368, abs=1e-4)
    assert black_scholes_delta(100, 100, 1, 0.20, 0.05, "PE") == pytest.approx(-0.3632, abs=1e-4)


def test_put_call_parity_holds():
    call = black_scholes_price(100, 100, 1, 0.20, 0.05, "CE")
    put = black_scholes_price(100, 100, 1, 0.20, 0.05, "PE")
    assert call - put == pytest.approx(100 - 100 * exp(-0.05), abs=1e-6)


def test_at_expiry_delta_is_the_step_function():
    assert black_scholes_delta(110, 100, 0, 0.2, 0.05, "CE") == 1.0
    assert black_scholes_delta(90, 100, 0, 0.2, 0.05, "CE") == 0.0
    assert black_scholes_delta(90, 100, 0, 0.2, 0.05, "PE") == -1.0


# --------------------------------------------------------------------------
# implied volatility round-trips
# --------------------------------------------------------------------------

@pytest.mark.parametrize("vol", [0.08, 0.15, 0.22, 0.40, 0.85])
@pytest.mark.parametrize("strike", [23500, 24000, 24500])
def test_implied_volatility_recovers_the_volatility_that_made_the_price(vol, strike):
    years = years_to_expiry(EXPIRY, NOW)
    premium = black_scholes_price(24050, strike, years, vol, 0.065, "CE")
    recovered = implied_volatility(premium, 24050, strike, years, 0.065, "CE")
    assert recovered == pytest.approx(vol, abs=1e-3)


def test_a_premium_below_intrinsic_has_no_solution():
    years = years_to_expiry(EXPIRY, NOW)
    # A 24050 spot against a 23000 strike is 1050 intrinsic; 500 is impossible.
    assert implied_volatility(500, 24050, 23000, years, 0.065, "CE") is None


def test_an_absurdly_rich_premium_has_no_solution():
    years = years_to_expiry(EXPIRY, NOW)
    assert implied_volatility(20000, 24050, 24000, years, 0.065, "CE") is None


@pytest.mark.parametrize("bad", [
    {"premium": 0}, {"premium": -5}, {"spot": 0}, {"strike": 0}, {"years": 0},
])
def test_degenerate_inputs_have_no_solution(bad):
    args = {"premium": 320.0, "spot": 24050.0, "strike": 24000.0, "years": 0.017, "rate": 0.065}
    args.update(bad)
    assert implied_volatility(option_type="CE", **args) is None


# --------------------------------------------------------------------------
# the expiry horizon
# --------------------------------------------------------------------------

def test_the_horizon_runs_to_the_1530_ist_cutoff():
    # 21 Aug 10:30 -> 27 Aug 15:30 is 6 days 5 hours.
    expected = (6 * 24 + 5) * 3600 / (365 * 24 * 3600)
    assert years_to_expiry(EXPIRY, NOW) == pytest.approx(expected, rel=1e-6)


def test_the_horizon_is_floored_not_negative():
    after = datetime(2026, 8, 28, 10, 0, tzinfo=IST)
    assert years_to_expiry(EXPIRY, after) > 0
    assert years_to_expiry(EXPIRY, after) < 1e-5


def test_a_naive_timestamp_is_read_as_ist():
    naive = datetime(2026, 8, 21, 10, 30)
    assert years_to_expiry(EXPIRY, naive) == pytest.approx(years_to_expiry(EXPIRY, NOW), rel=1e-9)


# --------------------------------------------------------------------------
# how the trade plan uses it
# --------------------------------------------------------------------------

def _signal():
    return Signal("LONG", "TREND", NOW, 24012, 23988, 24000, 40.0, 20.0, 2.0, 0.8, "t")


def _option(strike=24000, premium=320.0, delta=None, expiry="2026-08-27"):
    return OptionContract(f"CE{strike}", strike, expiry, "CE", ltp=premium, bid=premium - 1,
                          ask=premium + 1, lot_size=75, delta=delta, volume=5000, open_interest=50000)


@pytest.mark.parametrize("strike, premium, low, high", [
    (23500, 650.0, 0.70, 0.95),      # ITM: high delta
    (24000, 320.0, 0.45, 0.65),      # ATM: around a half
    (24500, 90.0, 0.10, 0.40),       # OTM: low delta
])
def test_the_plan_implies_a_delta_that_tracks_moneyness(strike, premium, low, high):
    plan = build_trade_plan(_signal(), _option(strike, premium), StrategyConfig(max_risk_inr=60000), spot=24050.0, now=NOW)
    assert plan.delta_source == "implied"
    implied = plan.premium_risk_per_share / plan.initial_risk_points
    assert low < implied < high


def test_a_broker_delta_is_preferred_over_the_model():
    plan = build_trade_plan(_signal(), _option(delta=0.55), StrategyConfig(max_risk_inr=60000), spot=24050.0, now=NOW)
    assert plan.delta_source == "broker"
    assert plan.delta_is_estimated is False
    assert plan.implied_volatility is None


@pytest.mark.parametrize("option, why", [
    (_option(expiry="not-a-date"), "unparseable expiry"),
    (_option(strike=23000, premium=5.0), "premium below intrinsic"),
])
def test_an_unsolvable_quote_falls_back_and_says_so(option, why):
    plan = build_trade_plan(_signal(), option, StrategyConfig(max_risk_inr=60000), spot=24050.0, now=NOW)
    assert plan.delta_source == "assumed", why
    assert plan.delta_is_estimated is True
    assert plan.premium_risk_per_share == pytest.approx(min(plan.initial_risk_points * 0.50, plan.entry_premium))


def test_the_implied_volatility_is_reported_with_the_plan():
    plan = build_trade_plan(_signal(), _option(), StrategyConfig(max_risk_inr=60000), spot=24050.0, now=NOW)
    assert plan.implied_volatility is not None
    assert 0.05 < plan.implied_volatility < 1.0
    assert plan.to_dict()["delta_source"] == "implied"


def test_an_implied_delta_moves_the_stop_the_broker_will_arm():
    """The whole point: a 0.25-delta OTM contract no longer gets a 0.50 stop."""
    otm = _option(24500, 90.0)
    implied = build_trade_plan(_signal(), otm, StrategyConfig(max_risk_inr=60000), spot=24050.0, now=NOW)
    assumed = build_trade_plan(_signal(), _option(24500, 90.0, expiry="not-a-date"),
                               StrategyConfig(max_risk_inr=60000), spot=24050.0, now=NOW)
    assert implied.stop_premium > assumed.stop_premium      # tighter, because delta is lower
    assert implied.premium_risk_per_share < assumed.premium_risk_per_share
