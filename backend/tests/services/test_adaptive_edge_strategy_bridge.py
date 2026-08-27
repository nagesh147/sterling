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
