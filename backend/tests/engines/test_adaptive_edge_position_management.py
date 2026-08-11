import pytest

from app.engines.adaptive_edge.position_management import (
    PositionPhase,
    PositionState,
    mark_to_market,
    propose_protection,
    request_exit,
)


def long_state(stop=99.0):
    return PositionState("p1", PositionPhase.OPEN, 1, 1.0, 100.0, 105.0, stop, 105.0)


def short_state(stop=101.0):
    return PositionState("p2", PositionPhase.OPEN, -1, 1.0, 100.0, 95.0, stop, 95.0)


def test_long_stop_cannot_loosen():
    decision = propose_protection(long_state(101.0), 100.0)
    assert decision.stop_price == 101.0


def test_short_stop_cannot_loosen():
    decision = propose_protection(short_state(99.0), 100.0)
    assert decision.stop_price == 99.0


def test_long_stop_cannot_exceed_market():
    with pytest.raises(ValueError):
        propose_protection(long_state(), 106.0)


def test_short_stop_cannot_be_below_market():
    with pytest.raises(ValueError):
        propose_protection(short_state(), 94.0)


def test_peak_profit_is_monotonic():
    state = mark_to_market(long_state(), 110.0)
    state = mark_to_market(state, 106.0)
    assert state.peak_price == 110.0
    assert state.peak_profit == 10.0


def test_exit_is_pending_and_requires_reason():
    decision = request_exit(long_state(), "edge_invalidated")
    assert decision.exit_requested
    assert decision.phase == PositionPhase.EXIT_PENDING
    with pytest.raises(ValueError):
        request_exit(long_state(), "")
