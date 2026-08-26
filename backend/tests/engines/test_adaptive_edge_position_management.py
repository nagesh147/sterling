import pytest

from app.engines.adaptive_edge.position_management import (
    PositionPhase,
    PositionState,
    current_pnl,
    mark_to_market,
    profit_giveback,
    propose_protection,
    request_exit,
)


def long_state(stop=99.0, realized_pnl=0.0, peak_profit=0.0):
    return PositionState("p1", PositionPhase.OPEN, 1, 1.0, 100.0, 105.0, stop, 105.0, realized_pnl, peak_profit)


def short_state(stop=101.0):
    return PositionState("p2", PositionPhase.OPEN, -1, 1.0, 100.0, 95.0, stop, 95.0)


def test_current_pnl_includes_realized_and_unrealized_pnl():
    assert current_pnl(long_state(realized_pnl=2.0)) == 7.0


def test_profit_giveback_is_peak_pnl_minus_current_pnl():
    state = long_state(peak_profit=10.0)
    assert profit_giveback(state) == 5.0


def test_peak_profit_is_monotonic():
    state = mark_to_market(long_state(), 110.0)
    state = mark_to_market(state, 106.0)
    assert state.peak_price == 110.0
    assert state.peak_profit == 10.0


def test_long_stop_cannot_loosen():
    assert propose_protection(long_state(101.0), 100.0) == 101.0


def test_short_stop_cannot_loosen():
    assert propose_protection(short_state(99.0), 100.0) == 99.0


def test_long_stop_cannot_exceed_market():
    with pytest.raises(ValueError):
        propose_protection(long_state(), 106.0)


def test_short_stop_cannot_be_below_market():
    with pytest.raises(ValueError):
        propose_protection(short_state(), 94.0)


def test_exit_intent_does_not_invent_an_exit_trigger():
    assert request_exit(long_state()) == PositionPhase.EXIT_INTENT
