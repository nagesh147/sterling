"""The bridge from the running engine to the canonical strategy pipeline.

Before this existed, nothing in app/services or app/api imported
strategy_pipeline — the specification's mathematics was implemented and the
engine that ran never called it. These tests pin that it is called, and that the
two things kept apart stay apart: the pipeline decides direction and economics,
the scanner decides the instrument.
"""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge import AdaptiveEdgeConfig
from app.services.adaptive_edge_strategy import (
    MIN_BARS,
    PipelineDecision,
    decide_from_candles,
    strategy_config_for,
)

BASE_MS = 1_756_100_000_000


def _series(n: int, slope: float) -> list[dict]:
    out = []
    for i in range(n):
        px = 25_000 + i * slope
        out.append({"timestamp_ms": BASE_MS + i * 60_000, "open": px, "high": px + 8,
                    "low": px - 8, "close": px + slope, "volume": 1_000 + (i % 7) * 250})
    return out


@pytest.fixture
def cfg():
    return AdaptiveEdgeConfig().validate()


# ------------------------------------------------------------- it is called

def test_the_pipeline_actually_runs_and_returns_a_decision(cfg):
    decision = decide_from_candles("NIFTY", _series(120, 5.0), cfg,
                                   expiry="2026-09-03", spot=25_600.0)
    assert isinstance(decision, PipelineDecision)
    assert decision.direction in ("BULLISH", "BEARISH", "NEUTRAL")
    assert decision.bars == 120
    assert decision.trace_hash, "a decision must be traceable to its inputs"


def test_a_rising_series_is_read_as_bullish(cfg):
    decision = decide_from_candles("NIFTY", _series(120, 5.0), cfg,
                                   expiry="2026-09-03", spot=25_600.0)
    assert decision.direction == "BULLISH"
    assert decision.option_type == "CE"


def test_direction_maps_to_the_contract_side():
    for direction, expected in (("BULLISH", "CE"), ("BEARISH", "PE"), ("NEUTRAL", None)):
        decision = PipelineDecision(
            underlying="NIFTY", direction=direction, horizon="MICRO", reason="",
            uncertainty=0.1, target_points=10, stop_points=5,
            expected_net_value=100.0, eligible=True, bars=100, trace_hash="h")
        assert decision.option_type == expected


# ------------------------------------------------------- not enough history

def test_too_little_history_returns_none_not_a_decision(cfg):
    """None is the engine not being in a position to ask. NEUTRAL is the
    strategy declining. Collapsing them would hide a data problem as a view."""
    assert decide_from_candles("NIFTY", _series(5, 5.0), cfg,
                               expiry="2026-09-03", spot=25_600.0) is None


def test_the_history_floor_is_enforced_at_the_boundary(cfg):
    assert decide_from_candles("NIFTY", _series(MIN_BARS - 1, 5.0), cfg,
                               expiry="2026-09-03", spot=25_600.0) is None
    assert decide_from_candles("NIFTY", _series(MIN_BARS, 5.0), cfg,
                               expiry="2026-09-03", spot=25_600.0) is not None


def test_an_empty_series_is_none_not_a_crash(cfg):
    assert decide_from_candles("NIFTY", [], cfg, expiry="2026-09-03", spot=25_600.0) is None


def test_a_pipeline_failure_is_an_absence_of_decision_not_a_crash(cfg, monkeypatch):
    """A scan must survive one underlying's pipeline blowing up."""
    import app.services.adaptive_edge_strategy as bridge

    def boom(*a, **k):
        raise RuntimeError("pipeline exploded")

    monkeypatch.setattr(bridge, "run_strategy_semantics_pipeline", boom)
    assert decide_from_candles("NIFTY", _series(120, 5.0), cfg,
                               expiry="2026-09-03", spot=25_600.0) is None


# ------------------------------------------------------------ actionability

def test_actionable_requires_both_a_direction_and_positive_expectancy():
    """Both terms are §35's, not tuning."""
    def make(direction, eligible):
        return PipelineDecision(
            underlying="N", direction=direction, horizon="MICRO", reason="",
            uncertainty=0.1, target_points=10, stop_points=5,
            expected_net_value=1.0, eligible=eligible, bars=100, trace_hash="h")

    assert make("BULLISH", True).actionable is True
    assert make("BULLISH", False).actionable is False
    assert make("NEUTRAL", True).actionable is False


# --------------------------------------------------------- config mapping

def test_engine_config_is_translated_not_assumed(cfg):
    """The engine's stop is a percentage of premium; the pipeline works in
    points. Passing one as the other would mean a stop off by the spot price."""
    mapped = strategy_config_for(cfg, symbol="NIFTY", expiry="2026-09-03", spot=25_000.0)
    assert mapped.symbol == "NIFTY"
    assert mapped.stop_points == pytest.approx(25_000.0 * cfg.stop_percent / 100.0)
    assert mapped.target_rr == cfg.target_multiple
    assert mapped.min_net_value == cfg.min_expected_net_value


def test_a_zero_spot_does_not_produce_a_zero_stop(cfg):
    """A zero stop is a position with no downside boundary."""
    assert strategy_config_for(cfg, symbol="NIFTY", expiry="2026-09-03", spot=0.0).stop_points > 0


# ------------------------------------------------- instrument separation

def test_the_synthesized_contract_is_carried_but_marked_as_reference_only(cfg):
    """select_option_contract builds a tradingsymbol by string formatting —
    hardcoded NIFTY prefix, 50-point step, guessed expiry code. Usable as a
    label, not as an order: a fabricated key rejects or hits a contract nobody
    chose. The field name has to say so."""
    decision = decide_from_candles("NIFTY", _series(120, 5.0), cfg,
                                   expiry="2026-09-03", spot=25_600.0)
    assert hasattr(decision, "reference_instrument")
    assert not hasattr(decision, "instrument"), (
        "a bare 'instrument' would read as tradeable; the synthesized symbol is not")


# ------------------------------------------- F-103 candidate eligibility

def test_f103_supplies_the_refusal_reason_rather_than_prose():
    """The reason an operator reads should come from the formula that owns the
    decision, not from a sentence written at the call site."""
    from app.services.adaptive_edge_scanner import _f103_eligibility

    result = _f103_eligibility({}, "BULLISH", 500.0, None)
    assert result.eligible is False
    assert result.reason == "missing_conservative_expected_value"
    assert result.formula_id == "F-103"


def test_f103_admits_a_candidate_once_the_bound_exists():
    """Proves the refusal is the missing input, not a disabled path."""
    from app.services.adaptive_edge_scanner import _f103_eligibility

    result = _f103_eligibility({}, "BULLISH", 500.0, 120.0)
    assert result.eligible is True
    assert result.action.value == "BUY_CE"


def test_f103_maps_a_bearish_decision_to_a_put():
    from app.services.adaptive_edge_scanner import _f103_eligibility
    assert _f103_eligibility({}, "BEARISH", 500.0, 90.0).action.value == "BUY_PE"


def test_f103_refuses_a_neutral_decision_before_looking_at_economics():
    from app.services.adaptive_edge_scanner import _f103_eligibility
    result = _f103_eligibility({}, "NEUTRAL", 500.0, 120.0)
    assert result.eligible is False
    assert result.reason == "no_directional_candidate"


def test_f103_refuses_a_non_positive_expected_value():
    from app.services.adaptive_edge_scanner import _f103_eligibility
    assert _f103_eligibility({}, "BULLISH", 0.0, 120.0).eligible is False


# ------------------------------------------------ F-109 contract ranking

def _contract(symbol, oi, strike, premium=120.0):
    return {"symbol": symbol, "oi": oi, "strike": strike, "spot": 25_000.0,
            "last_price": premium, "bid": premium - 1, "ask": premium + 1,
            "lot_size": 50, "option_type": "CE"}


def test_ranking_falls_back_to_liquidity_when_f109_cannot_decide(cfg):
    """F-109 needs expected value per contract, which needs the probability
    model. The fallback is a liquidity heuristic and is named as one rather
    than presented as the formula."""
    from app.services.adaptive_edge_scanner import rank_contracts

    rows = [_contract("THIN", 100, 25_000), _contract("DEEP", 900, 25_100)]
    assert [r["symbol"] for r in rank_contracts(rows, cfg, expected_ev=None)] == ["DEEP", "THIN"]


def test_f109_puts_its_choice_first_when_it_can_decide(cfg):
    from app.services.adaptive_edge_scanner import rank_contracts

    rows = [_contract("A", 60_000, 25_000), _contract("B", 90_000, 25_100)]
    ranked = rank_contracts(rows, cfg, expected_ev=5_000.0)
    assert len(ranked) == len(rows), "ranking must not drop contracts"
    assert {r["symbol"] for r in ranked} == {"A", "B"}


def test_ranking_never_drops_contracts_the_recorder_needs(cfg):
    """Being surfaced is not being armable. Observations are what calibration
    consumes, so a contract F-109 declines must still reach the recorder."""
    from app.services.adaptive_edge_scanner import rank_contracts

    rows = [_contract("X", 10, 25_000, premium=1.0)]   # fails every constraint
    assert len(rank_contracts(rows, cfg, expected_ev=5_000.0)) == 1


# ------------------------------------------------ F-105 conservative EV

def test_conservative_ev_is_a_real_lower_bound_not_a_scaled_guess():
    """net_ev - z * standard_error, where the error is the finite-sample spread
    of the payoff. Widening the sample must tighten the bound toward net EV."""
    from app.services.adaptive_edge_strategy import conservative_ev

    small = conservative_ev(premium=120.0, target_price=240.0, stop_price=84.0,
                            p_target=0.30, p_stop=0.20, execution_cost=2.0, sample_size=50)
    large = conservative_ev(premium=120.0, target_price=240.0, stop_price=84.0,
                            p_target=0.30, p_stop=0.20, execution_cost=2.0, sample_size=50_000)
    assert small.conservative_ev < large.conservative_ev
    assert large.conservative_ev < large.net_ev


def test_the_signature_cannot_take_directional_probabilities():
    """The guard against a category error that manufactured positive expectancy.

    An earlier version took F-102's class probabilities and mapped P(UP) to
    p_target for a call. P(UP) is "the underlying moves 8 bps in 15 bars";
    target_price is "the premium doubles". Those are different events, and with
    the measured no-edge probabilities (P(UP) 0.185 against P(DOWN) 0.207 — a
    losing hit rate) that mapping returned conservative_ev = +11.61, eligible.

    Keeping the parameters explicit and unnamed-by-direction is what stops it
    being made again by accident.
    """
    import inspect
    from app.services.adaptive_edge_strategy import conservative_ev

    params = set(inspect.signature(conservative_ev).parameters)
    assert "p_target" in params and "p_stop" in params
    assert "direction" not in params, "a direction argument invites the class-probability mapping"
    assert "probabilities" not in params


def test_a_losing_setup_is_refused():
    from app.services.adaptive_edge_strategy import conservative_ev
    result = conservative_ev(premium=120.0, target_price=240.0, stop_price=84.0,
                             p_target=0.05, p_stop=0.60, execution_cost=2.0, sample_size=8_000)
    assert result.eligible is False
    assert result.conservative_ev < 0


def test_probabilities_that_exceed_certainty_are_refused():
    from app.services.adaptive_edge_strategy import conservative_ev
    assert conservative_ev(premium=120.0, target_price=240.0, stop_price=84.0,
                           p_target=0.7, p_stop=0.7, execution_cost=2.0,
                           sample_size=8_000) is None


def test_an_inverted_target_is_refused_rather_than_priced():
    """A long option's target is above entry and its stop below. Anything else
    is a different instrument being priced as this one."""
    from app.services.adaptive_edge_strategy import conservative_ev
    assert conservative_ev(premium=120.0, target_price=80.0, stop_price=84.0,
                           p_target=0.3, p_stop=0.2, execution_cost=2.0,
                           sample_size=8_000) is None


def test_excursion_probabilities_need_enough_resolved_observations():
    """A bound computed on a handful of rows is a number, not a bound."""
    from app.services.adaptive_edge_strategy import premium_excursion_probabilities

    thin = [{"forward_return_pct": 5.0, "max_favourable_pct": 5.0, "max_adverse_pct": -2.0}] * 10
    assert premium_excursion_probabilities(thin, target_multiple=2.0, stop_percent=30.0) is None


def test_excursion_probabilities_are_measured_from_what_happened():
    from app.services.adaptive_edge_strategy import premium_excursion_probabilities

    winners = [{"forward_return_pct": 120.0, "max_favourable_pct": 120.0, "max_adverse_pct": -5.0}] * 100
    losers = [{"forward_return_pct": -40.0, "max_favourable_pct": 3.0, "max_adverse_pct": -40.0}] * 150
    result = premium_excursion_probabilities(winners + losers, target_multiple=2.0, stop_percent=30.0)
    assert result is not None
    p_target, p_stop, n = result
    assert n == 250
    assert p_target == pytest.approx(100 / 250)
    assert p_stop == pytest.approx(150 / 250)


def test_unresolved_observations_are_excluded_from_the_estimate():
    """An observation with no outcome yet says nothing about excursion."""
    from app.services.adaptive_edge_strategy import premium_excursion_probabilities

    pending = [{"forward_return_pct": None}] * 500
    assert premium_excursion_probabilities(pending, target_multiple=2.0, stop_percent=30.0) is None


# ----------------------------------------------------- straddle signal

def _leg(strike, kind, price, symbol=None):
    return {"strike": strike, "option_type": kind, "symbol": symbol or f"{kind}{strike}",
            "last_price": price, "lot_size": 75, "token": abs(hash((strike, kind))) % 9999,
            "expiry": "2026-09-03"}


def _chain():
    return [_leg(24_800, "CE", 25.0), _leg(24_800, "PE", 22.0),
            _leg(25_000, "CE", 8.0), _leg(25_000, "PE", 60.0)]


def _prices(sigma: float, n: int = 45, seed: int = 3) -> list[float]:
    import random
    rng = random.Random(seed)
    out = [24_800.0]
    for _ in range(n):
        out.append(out[-1] * (1.0 + rng.gauss(0.0, sigma)))
    return out


def test_the_atm_pair_shares_one_strike():
    """A straddle whose legs sit at different strikes is a strangle with
    different economics."""
    from app.services.adaptive_edge_scanner import atm_pair

    call, put = atm_pair(_chain(), 24_810.0)
    assert call["strike"] == put["strike"] == 24_800


def test_a_strike_with_only_one_side_is_not_a_straddle():
    from app.services.adaptive_edge_scanner import atm_pair
    assert atm_pair([_leg(25_000, "CE", 8.0)], 25_000.0) == (None, None)


def test_an_active_tape_against_a_cheap_straddle_is_armable(cfg):
    from app.services.adaptive_edge_scanner import straddle_signal

    signal = straddle_signal("NIFTY", _chain(), _prices(0.0009), cfg, spot=24_810.0)
    assert signal["entry_ok"] is True
    assert signal["edge_ratio"] > 1.0
    assert signal["structure"] == "STRADDLE"


def test_a_quiet_tape_against_the_same_straddle_is_refused(cfg):
    """The comparison is the strategy: movement has to be cheaper than it is
    likely, and on a quiet tape it is not."""
    from app.services.adaptive_edge_scanner import straddle_signal

    signal = straddle_signal("NIFTY", _chain(), _prices(0.00008), cfg, spot=24_810.0)
    assert signal["entry_ok"] is False
    assert "already prices more movement" in signal["reason"]


def test_an_expensive_straddle_is_refused_on_the_same_tape(cfg):
    from app.services.adaptive_edge_scanner import straddle_signal

    dear = [_leg(24_800, "CE", 180.0), _leg(24_800, "PE", 175.0)]
    signal = straddle_signal("NIFTY", dear, _prices(0.0009), cfg, spot=24_810.0)
    assert signal["entry_ok"] is False


def test_too_little_history_is_no_signal_rather_than_a_refusal(cfg):
    """None is the engine unable to ask. An ineligible signal would say it
    asked and the answer was no."""
    from app.services.adaptive_edge_scanner import straddle_signal
    assert straddle_signal("NIFTY", _chain(), [24_800.0] * 5, cfg, spot=24_810.0) is None


def test_an_unpriceable_chain_is_no_signal(cfg):
    from app.services.adaptive_edge_scanner import straddle_signal
    assert straddle_signal("NIFTY", [], _prices(0.0009), cfg, spot=24_810.0) is None


def test_the_signal_shows_both_sides_of_the_comparison(cfg):
    """An operator needs what the market asked and what the engine expected."""
    from app.services.adaptive_edge_scanner import straddle_signal

    signal = straddle_signal("NIFTY", _chain(), _prices(0.0009), cfg, spot=24_810.0)
    assert signal["forecast_bps"] > 0
    assert signal["breakeven_bps"] > 0
    assert signal["realised_vol_bps"] > 0
    assert 0.0 < signal["vol_percentile"] <= 1.0
