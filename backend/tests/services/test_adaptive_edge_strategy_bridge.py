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
