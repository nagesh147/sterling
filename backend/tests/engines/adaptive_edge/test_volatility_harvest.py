"""Selling volatility, defined risk only.

The findings this guards invert the usual intuition twice: sell into movement
rather than into calm, and never let the forecast argue that a tail will not
arrive. The tests are written so that regressing either one fails loudly.
"""
from __future__ import annotations

import math
import random

import pytest

from app.engines.adaptive_edge.volatility_harvest import (
    from_quotes,
    ATM_STRADDLE_COEFFICIENT,
    MIN_FORECAST_PERCENTILE,
    WING_DISTANCE_SD,
    VolatilityHarvestError,
    evaluate,
    strangle_value,
)


def _series(sigma: float, n: int = 45, start: float = 24_800.0, seed: int = 4) -> list[float]:
    rng = random.Random(seed)
    out = [start]
    for _ in range(n):
        out.append(out[-1] * (1.0 + rng.gauss(0.0, sigma)))
    return out


QUIET, NORMAL, ACTIVE = 0.00008, 0.0004, 0.0011


# ------------------------------------------------------- defined risk only

def test_naked_selling_is_structurally_impossible():
    """Not a flag, not a default — there is no path to an uncapped position.

    A naked seller loses 18.8 times the credit on a 6% move and 42 times on a
    13% one, and a stop does not help because a gap opens through it.
    """
    with pytest.raises(VolatilityHarvestError, match="does not sell naked"):
        evaluate(_series(ACTIVE), implied_vol_ratio=1.2, wing_sd=0.0)
    with pytest.raises(VolatilityHarvestError):
        evaluate(_series(ACTIVE), implied_vol_ratio=1.2, wing_sd=-1.0)


def test_every_eligible_structure_has_a_finite_capped_loss():
    for sigma in (NORMAL, ACTIVE):
        result = evaluate(_series(sigma), implied_vol_ratio=1.2)
        assert result.max_loss_bps > 0
        assert math.isfinite(result.max_loss_bps)
        assert result.shock_loss_multiple < 5.0, "a capped structure must not risk many credits"


def test_wider_wings_cost_less_but_risk_more():
    tight = evaluate(_series(ACTIVE), implied_vol_ratio=1.2, wing_sd=1.0)
    wide = evaluate(_series(ACTIVE), implied_vol_ratio=1.2, wing_sd=3.0)
    assert wide.net_credit_bps > tight.net_credit_bps
    assert wide.max_loss_bps > tight.max_loss_bps


# ------------------------------------------------ sell movement, not calm

def test_quiet_tape_is_refused():
    """The inversion. Selling into calm earned +0.18 bps in the study against
    +13.8 for the active decile, and carried a 7.1x tail-to-premium against
    1.8x. Quiet is the dangerous side, not the safe one."""
    result = evaluate(_series(QUIET), implied_vol_ratio=1.2)
    assert result.eligible is False
    assert "does not cover the tail" in result.reason


def test_active_tape_is_taken():
    result = evaluate(_series(ACTIVE), implied_vol_ratio=1.2)
    assert result.eligible is True
    assert result.forecast_percentile >= MIN_FORECAST_PERCENTILE


def test_the_percentile_floor_is_what_decides():
    quiet = _series(QUIET)
    assert evaluate(quiet, implied_vol_ratio=1.2).eligible is False
    # Drop the floor and the same tape becomes eligible: the refusal is the
    # percentile rule, not some other accident.
    assert evaluate(quiet, implied_vol_ratio=1.2, min_percentile=0.0).eligible is True


# --------------------------------------------- the implied ratio is required

def test_the_implied_ratio_must_be_supplied():
    """The entire expectancy is proportional to it. A default would let a
    research assumption reach a trading decision."""
    import inspect
    params = inspect.signature(evaluate).parameters
    assert params["implied_vol_ratio"].default is inspect.Parameter.empty


def test_a_non_positive_implied_ratio_is_refused():
    with pytest.raises(VolatilityHarvestError, match="measured from live quotes"):
        evaluate(_series(ACTIVE), implied_vol_ratio=0.0)


def test_credit_scales_with_the_implied_ratio():
    thin = evaluate(_series(ACTIVE), implied_vol_ratio=0.9)
    fat = evaluate(_series(ACTIVE), implied_vol_ratio=1.5)
    assert fat.net_credit_bps > thin.net_credit_bps


# ------------------------------------------------------- the wing pricing

def test_wings_cost_something():
    """Omitting this made a defined-risk structure look like it could never
    lose, which is impossible and was the tell that the model was wrong."""
    assert strangle_value(100.0, 150.0) > 0


def test_further_wings_cost_less():
    assert strangle_value(100.0, 300.0) < strangle_value(100.0, 100.0)


def test_the_net_credit_is_below_the_gross_straddle():
    result = evaluate(_series(ACTIVE), implied_vol_ratio=1.2)
    sd = 1.2 * result.realised_vol_bps * math.sqrt(30)
    assert result.net_credit_bps < ATM_STRADDLE_COEFFICIENT * sd


def test_a_zero_standard_deviation_costs_nothing():
    assert strangle_value(0.0, 100.0) == 0.0


# ------------------------------------------------------------- boundaries

def test_too_little_history_is_no_answer_rather_than_a_refusal():
    """None is the engine unable to ask. An ineligible structure would say it
    asked and declined."""
    assert evaluate([24_800.0] * 5, implied_vol_ratio=1.2) is None


def test_the_shipped_wing_distance_is_the_measured_one():
    """1.5 sd keeps 89% of the naked expectancy and caps a 6% shock at one
    credit instead of 18.8. Changing it silently changes the risk profile."""
    assert WING_DISTANCE_SD == 1.5


def test_the_structure_reports_what_an_operator_needs_to_size():
    result = evaluate(_series(ACTIVE), implied_vol_ratio=1.2)
    assert result.net_credit_bps > 0
    assert result.max_loss_bps > 0
    assert 0 < result.credit_to_risk
    assert result.forecast_bps > 0
    assert result.realised_vol_bps > 0


# ------------------------------------- the payoff assumption, and its limits

def test_the_module_does_not_claim_to_be_validated():
    """The study's expectancy measured options expiring at the horizon.

    `P&L = credit - |move|` is a held-to-expiry payoff. A thirty-minute-to-expiry
    NIFTY option mostly is not listed, so a t-statistic of 10.9 built from 585
    such windows is answering a question about contracts that do not exist. On
    the tradeable subset — expiry sessions held to the close — the result is
    +0.09 bps at t=0.02 over 27 sessions.

    Anyone reaching for this module must meet that in the first paragraph.
    """
    from app.engines.adaptive_edge import volatility_harvest as module

    doc = module.__doc__ or ""
    assert "NOT a validated strategy" in doc
    assert "expires at the end of the horizon" in doc
    assert "27" in doc, "the tradeable-subset sample size must be stated"


def test_a_short_hold_on_a_dated_option_is_not_the_modelled_payoff():
    """Guards the arithmetic behind the correction.

    A seven-day straddle decays a fraction of a percent of its premium over
    thirty minutes while carrying the whole move. Premium collection and
    gamma exposure are different trades, and conflating them is what made the
    study look conclusive.
    """
    minutes_per_year = 375 * 250

    def straddle(iv: float, years: float) -> float:
        return ATM_STRADDLE_COEFFICIENT * iv * math.sqrt(years) * 10_000

    seven_day = 7 / 250
    full = straddle(0.12, seven_day)
    after_30_min = straddle(0.12, seven_day - 30 / minutes_per_year)
    decay_fraction = (full - after_30_min) / full
    assert decay_fraction < 0.02, (
        "a 30-minute hold on a 7-day option collects almost no premium; if this "
        "ever exceeds a couple of percent the correction above needs revisiting")

    # Whereas an option expiring at the horizon surrenders essentially all of it.
    expiring = straddle(0.12, 30 / minutes_per_year)
    assert expiring > 0


# ------------------------------------------------- pricing from live quotes

def _quoted(**over):
    kwargs = dict(call_premium=21.0, put_premium=19.0, spot=24_800.0,
                  minutes_to_expiry=30.0, horizon_bars=30)
    kwargs.update(over)
    return from_quotes(_series(ACTIVE), **kwargs)


def test_the_runtime_path_prices_from_the_quoted_premium():
    """No assumed ratio reaches a trade: the credit is what the market shows."""
    result = _quoted()
    assert result is not None and result.eligible is True
    # 40 points on 24,800 is ~16.1 bps gross; net is that minus the wings.
    assert 0 < result.net_credit_bps < 16.2


def test_a_dearer_quote_gives_a_larger_credit():
    assert _quoted(call_premium=40, put_premium=38).net_credit_bps > _quoted().net_credit_bps


def test_a_contract_outliving_the_hold_is_refused():
    """`credit - |move|` is only the payoff when the option settles at the end
    of the hold. A 3-day option held 30 minutes is a mark-to-market on gamma and
    theta — a different trade with a different sign, and pricing it as premium
    collection is the error that made the offline study look conclusive."""
    with pytest.raises(VolatilityHarvestError, match="holding to expiry"):
        _quoted(minutes_to_expiry=3 * 375)


def test_a_hold_matching_expiry_is_accepted():
    assert _quoted(minutes_to_expiry=30.0) is not None
    assert _quoted(minutes_to_expiry=29.0) is not None


def test_an_expired_or_unpriced_contract_gives_nothing():
    assert _quoted(minutes_to_expiry=0.0) is None
    assert _quoted(call_premium=0.0) is None
    assert _quoted(spot=0.0) is None


def test_the_runtime_path_still_refuses_to_sell_naked():
    with pytest.raises(VolatilityHarvestError, match="does not sell naked"):
        _quoted(wing_sd=0.0)


def test_the_runtime_path_still_applies_the_percentile_floor():
    quiet = from_quotes(_series(QUIET), call_premium=21.0, put_premium=19.0,
                        spot=24_800.0, minutes_to_expiry=30.0, horizon_bars=30)
    assert quiet.eligible is False
    assert "does not cover the tail" in quiet.reason


def test_the_research_path_is_labelled_as_such():
    """evaluate() still derives the credit from sqrt(horizon), which models an
    option expiring at the horizon. That is fine for uniform study work and is
    not what should price a trade."""
    assert "expiring at the horizon" in (evaluate.__doc__ or "")
    assert "from_quotes" in (evaluate.__doc__ or "")
