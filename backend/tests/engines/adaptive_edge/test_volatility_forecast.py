"""The signal the engine actually trades on.

Direction was tested and abandoned on evidence — see VOLATILITY_EDGE.md. What is
left is a forecast of how far the tape will travel, and a live comparison
against what the straddle charges for that travel. These tests guard both.
"""
from __future__ import annotations

import math
import random

import pytest

from app.engines.adaptive_edge.volatility_forecast import (
    EXCURSION_MULTIPLE,
    HORIZON_BARS,
    MIN_HISTORY_BARS,
    evaluate_straddle,
    forecast,
    realised_vol_bps,
)


def _series(sigma: float, n: int = 60, start: float = 24_800.0, seed: int = 11) -> list[float]:
    rng = random.Random(seed)
    out = [start]
    for _ in range(n):
        out.append(out[-1] * (1.0 + rng.gauss(0.0, sigma)))
    return out


# --------------------------------------------------------- realised vol

def test_realised_vol_is_none_without_enough_history():
    """None and zero are different answers. Zero is a tape that did not move;
    None is not being able to tell, and collapsing them makes the forecast say
    "nothing will happen" when it means "I do not know"."""
    assert realised_vol_bps([24_800.0, 24_801.0]) is None


def test_realised_vol_rises_with_dispersion():
    quiet = realised_vol_bps(_series(0.00015))
    active = realised_vol_bps(_series(0.0009))
    assert quiet is not None and active is not None
    assert active > quiet * 3


def test_non_positive_prices_are_discarded_not_treated_as_zero():
    series = _series(0.0004)
    series[5] = 0.0
    series[9] = -1.0
    assert realised_vol_bps(series) is not None


# ------------------------------------------------------------- forecast

def test_forecast_scales_with_volatility():
    quiet = forecast(_series(0.00015))
    active = forecast(_series(0.0009))
    assert quiet is not None and active is not None
    assert active.excursion_bps > quiet.excursion_bps * 3


def test_forecast_uses_the_measured_multiple():
    """4.6775 is the median excursion-per-unit-volatility over 48,174 rows. A
    silent change to it rescales every forecast and therefore every trade."""
    result = forecast(_series(0.0005))
    assert result is not None
    assert result.excursion_bps == pytest.approx(EXCURSION_MULTIPLE * result.realised_vol_bps)


def test_the_multiple_sits_below_random_walk_scaling():
    """sqrt(30) = 5.477 for a pure random walk. The measured 4.68 is lower,
    which is the damping a mean-reverting tape produces — and the reason this is
    fitted rather than assumed."""
    assert EXCURSION_MULTIPLE < math.sqrt(HORIZON_BARS)


def test_a_longer_horizon_forecasts_a_larger_excursion():
    base = forecast(_series(0.0005), horizon_bars=HORIZON_BARS)
    longer = forecast(_series(0.0005), horizon_bars=HORIZON_BARS * 4)
    assert longer.excursion_bps == pytest.approx(base.excursion_bps * 2.0, rel=1e-6)


def test_forecast_is_none_without_enough_history():
    assert forecast([24_800.0] * (MIN_HISTORY_BARS - 5)) is None


def test_quiet_and_active_are_mutually_exclusive():
    for sigma in (0.00005, 0.0002, 0.0005, 0.002):
        result = forecast(_series(sigma))
        assert not (result.is_quiet and result.is_active)


# -------------------------------------------------------- straddle gate

def _gate(forecast_bps: float, call: float, put: float, spot: float = 24_800.0, **kw):
    return evaluate_straddle(forecast_bps=forecast_bps, call_premium=call,
                             put_premium=put, spot=spot, **kw)


def test_an_expensive_straddle_is_refused():
    """The premium already prices more movement than the tape is expected to
    deliver. This is the whole strategy in one comparison."""
    gate = _gate(46.0, 95.0, 90.0)
    assert gate.eligible is False
    assert "already prices more movement" in gate.reason


def test_a_cheap_straddle_clears():
    gate = _gate(46.0, 25.0, 22.0)
    assert gate.eligible is True
    assert gate.edge_ratio > 2.0


def test_the_margin_is_applied_and_is_not_cosmetic():
    """The forecast ranks at 0.29, not 1.0. Trading at exactly breakeven is a
    coin flip on an estimate, so the margin has to bite."""
    # Breakeven for a 47-point straddle on 24,800 is ~19.1 bps. A 21 bps
    # forecast clears it outright and fails the 1.25x requirement, which is
    # exactly the band the margin exists to refuse.
    just_above = _gate(21.0, 23.5, 23.5, margin=1.0)
    assert just_above.eligible is True
    same_forecast_with_margin = _gate(21.0, 23.5, 23.5, margin=1.25)
    assert same_forecast_with_margin.eligible is False


def test_round_trip_costs_are_inside_the_breakeven():
    """A breakeven that ignores the spread is not a breakeven — it is paid on
    the way in and again on the way out."""
    free = _gate(30.0, 25.0, 22.0, round_trip_cost_pct=0.0)
    costed = _gate(30.0, 25.0, 22.0, round_trip_cost_pct=5.0)
    assert costed.breakeven_bps > free.breakeven_bps


def test_an_unpriced_straddle_is_refused_not_guessed():
    assert _gate(50.0, 0.0, 22.0).eligible is False
    assert _gate(50.0, 25.0, 0.0).eligible is False
    assert "not priced" in _gate(50.0, 0.0, 0.0).reason


def test_a_missing_spot_is_refused():
    assert _gate(50.0, 25.0, 22.0, spot=0.0).eligible is False


def test_no_forecast_means_no_trade():
    gate = _gate(0.0, 25.0, 22.0)
    assert gate.eligible is False and gate.reason == "no forecast"


def test_the_gate_carries_both_numbers_it_compared():
    """An operator has to be able to see what the market asked and what the
    engine expected, not just the verdict."""
    gate = _gate(46.0, 25.0, 22.0)
    assert gate.forecast_bps == 46.0
    assert gate.breakeven_bps > 0
    assert gate.edge_ratio == pytest.approx(gate.forecast_bps / gate.breakeven_bps)


def test_the_gate_needs_live_premiums_and_assumes_no_volatility_level():
    """No fitted implied volatility may be baked in.

    An earlier version of this test string-matched "implied_vol" in the source,
    which broke the moment the gate started *reporting* an implied/realised
    ratio — a computed number from live quotes, which is the opposite of a
    hardcoded one. The property that matters is that the decision cannot be made
    without a current premium.
    """
    import inspect
    from app.engines.adaptive_edge import volatility_forecast as module

    params = inspect.signature(evaluate_straddle).parameters
    assert "call_premium" in params and "put_premium" in params
    for name in ("call_premium", "put_premium", "spot"):
        assert params[name].default is inspect.Parameter.empty, (
            f"{name} must be supplied from a live quote, not defaulted")
    # No module constant looks like an annualised volatility level.
    for key, value in vars(module).items():
        if key.isupper() and isinstance(value, float):
            assert not (0.05 <= value <= 0.60) or key == "ATM_STRADDLE_COEFFICIENT", (
                f"{key}={value} looks like a hardcoded volatility level")


def test_the_gate_reports_the_volatility_condition_it_applied():
    """The whole decision collapses to one ratio, and an operator should see it
    rather than infer it from two rupee figures."""
    dear = evaluate_straddle(forecast_bps=46.0, call_premium=95.0, put_premium=90.0, spot=24_800.0)
    cheap = evaluate_straddle(forecast_bps=46.0, call_premium=25.0, put_premium=22.0, spot=24_800.0)
    assert dear.implied_vol_ratio > dear.max_iv_ratio
    assert cheap.implied_vol_ratio < cheap.max_iv_ratio
    assert "implied/realised" in dear.reason


def test_the_threshold_tightens_as_the_margin_rises():
    from app.engines.adaptive_edge.volatility_forecast import max_implied_vol_ratio
    assert max_implied_vol_ratio(1.0) > max_implied_vol_ratio(1.25) > max_implied_vol_ratio(1.5)


def test_a_long_straddle_needs_options_cheaper_than_the_tape():
    """At the fitted multiple and a 1.25 margin the ceiling is ~0.86, so implied
    has to sit BELOW realised. Index options normally carry the opposite — the
    variance risk premium — which is why this gate refuses most of the time.
    That is the strategy declining a structurally losing trade, by design."""
    from app.engines.adaptive_edge.volatility_forecast import max_implied_vol_ratio
    assert max_implied_vol_ratio(1.25) < 1.0


def test_a_per_instrument_multiple_is_honoured():
    """Cross-validation put the multiple between 2.96 and 5.03 across 120
    instruments, so a caller with its own measurement must be able to use it."""
    lively = forecast(_series(0.0005), multiple=5.03)
    damped = forecast(_series(0.0005), multiple=2.96)
    assert lively.excursion_bps > damped.excursion_bps
