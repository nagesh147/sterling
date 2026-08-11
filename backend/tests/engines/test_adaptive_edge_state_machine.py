import pytest

from app.engines.adaptive_edge.state_machine import Event, StrategyState, transition


def test_entry_lifecycle_is_explicit():
    assert transition(StrategyState.FLAT, Event.OPPORTUNITY).current == StrategyState.CANDIDATE
    assert transition(StrategyState.CANDIDATE, Event.AUTHORIZED).current == StrategyState.AUTHORIZED
    assert transition(StrategyState.AUTHORIZED, Event.ENTRY_INTENT).current == StrategyState.ENTRY_PENDING
    assert transition(StrategyState.ENTRY_PENDING, Event.FILL).current == StrategyState.OPEN


def test_rejected_entry_creates_no_position():
    assert transition(StrategyState.ENTRY_PENDING, Event.REJECTED).current == StrategyState.FLAT


def test_exit_rejection_preserves_position():
    assert transition(StrategyState.EXIT_PENDING, Event.REJECTED).current == StrategyState.OPEN


def test_invalid_transition_is_rejected():
    with pytest.raises(ValueError):
        transition(StrategyState.FLAT, Event.FILL)
