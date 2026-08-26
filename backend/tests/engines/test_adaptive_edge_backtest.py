"""The backtester must not become a second strategy implementation.

This file used to drive a different `run_replay` — one taking bars that carried
`MarketFeatures` and no decision function, so the replay layer had to turn
features into a direction itself. The formulas that did that (F-101..F-114) were
removed as invented: `model.py` says they are "NOT part of the Master
Mathematical Specification and must not execute", and
`test_adaptive_edge_model.py` asserts they cannot reach an execution path.

So those tests could only have been made green by writing the strategy back,
which is the one thing the removal was for. They are replaced by tests that hold
the boundary open instead: bars carry data, callers supply decisions, and the
deprecated model still refuses to run.
"""
import pytest

from app.engines.adaptive_edge.backtest import ReplayBar, ReplayObservation, run_replay
from app.engines.adaptive_edge.model import MarketFeatures, ProvisionalAdaptiveEdgeModelError, f101_feature_score


def features(direction: float = 1.0) -> MarketFeatures:
    return MarketFeatures(
        trend=direction,
        momentum=direction,
        relative_volume=0.5,
        volatility_expansion=0.2,
        expected_move=2.0,
        confidence=0.9,
    )


def test_replay_bar_carries_data_and_decides_nothing():
    """A bar is market state. It must expose no way to act on itself."""
    bar = ReplayBar(close=100.0, spread_bps=4.0, atr=1.0, features=features())
    assert bar.close == 100.0
    assert bar.features.trend == 1.0
    for name in ("direction", "decide", "signal", "edge_score", "decision"):
        assert not hasattr(bar, name), f"ReplayBar grew a decision surface: {name}"


def test_replay_bars_compare_by_value_so_replays_are_comparable():
    assert ReplayBar(100.0, 4.0, 1.0, features()) == ReplayBar(100.0, 4.0, 1.0, features())
    assert ReplayBar(100.0, 4.0, 1.0, features(1.0)) != ReplayBar(100.0, 4.0, 1.0, features(-1.0))


def test_run_replay_will_not_invent_decisions_from_features():
    """There is no bar-and-config overload, and there must not be one.

    `run_replay` requires an explicit decision function. Calling it with bars
    alone fails rather than falling back to deriving a direction internally.
    """
    bars = [ReplayBar(close=100.0, spread_bps=4.0, atr=1.0, features=features()) for _ in range(20)]
    with pytest.raises(TypeError):
        run_replay(bars)


def test_replay_with_a_flat_decision_function_moves_no_capital():
    """The one honest end-to-end check left: no decision, no capital movement."""
    observations = [
        ReplayObservation(
            timestamp=f"2026-08-17T09:{minute:02d}:00+05:30",
            close=100.0,
            bid=99.9,
            ask=100.1,
            initial_stop=99.0,
            point_value=1.0,
            lot_size=1,
        )
        for minute in range(20)
    ]
    result = run_replay(observations, lambda observation, capital: None)
    assert result.trades == ()
    assert result.final_capital == result.initial_capital


def test_deprecated_feature_score_still_refuses_to_run():
    """If this ever stops raising, the invented model came back."""
    with pytest.raises(ProvisionalAdaptiveEdgeModelError):
        f101_feature_score(features())
