import pytest

from app.engines.adaptive_edge.state_machine import Event, StrategyState, transition


def test_entry_lifecycle_is_explicit():
    assert transition(StrategyState.OBSERVATION, Event.OPPORTUNITY).current == StrategyState.CANDIDATE
    assert transition(StrategyState.CANDIDATE, Event.EVALUATED).current == StrategyState.EVALUATED
    assert transition(StrategyState.EVALUATED, Event.AUTHORIZED).current == StrategyState.AUTHORIZED
    assert transition(StrategyState.AUTHORIZED, Event.ENTRY_INTENT).current == StrategyState.INTENT
    assert transition(StrategyState.INTENT, Event.ORDER_SUBMITTED).current == StrategyState.ORDERED
    assert transition(StrategyState.ORDERED, Event.FILL).current == StrategyState.OPEN


def test_partial_fill_is_explicit():
    assert transition(StrategyState.ORDERED, Event.PARTIAL_FILL).current == StrategyState.PARTIALLY_FILLED
    assert transition(StrategyState.PARTIALLY_FILLED, Event.FILL).current == StrategyState.OPEN


def test_rejected_entry_creates_no_open_position():
    assert transition(StrategyState.ORDERED, Event.REJECTED).current == StrategyState.REJECTED


def test_exit_rejection_preserves_position():
    assert transition(StrategyState.EXIT_INTENT, Event.REJECTED).current == StrategyState.OPEN


def test_invalid_transition_is_rejected():
    with pytest.raises(ValueError):
        transition(StrategyState.OBSERVATION, Event.FILL)
