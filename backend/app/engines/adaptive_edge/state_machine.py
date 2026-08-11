"""Adaptive Edge strategy lifecycle state machine.

The lifecycle mirrors the Master Specification's conceptual states while
keeping broker truth separate from strategy intent and fill events.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StrategyState(str, Enum):
    OBSERVATION = "OBSERVATION"
    # Backward-compatible name for callers that used the earlier lifecycle.
    FLAT = "OBSERVATION"
    CANDIDATE = "CANDIDATE"
    EVALUATED = "EVALUATED"
    AUTHORIZED = "AUTHORIZED"
    INTENT = "INTENT"
    ORDERED = "ORDERED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    OPEN = "OPEN"
    PROTECTING = "PROTECTING"
    EXIT_INTENT = "EXIT_INTENT"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class Event(str, Enum):
    OPPORTUNITY = "OPPORTUNITY"
    EVALUATED = "EVALUATED"
    AUTHORIZED = "AUTHORIZED"
    ENTRY_INTENT = "ENTRY_INTENT"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILL = "FILL"
    PROTECTION_UPDATED = "PROTECTION_UPDATED"
    EXIT_INTENT = "EXIT_INTENT"
    EXIT_FILL = "EXIT_FILL"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class StateTransition:
    previous: StrategyState
    event: Event
    current: StrategyState


_ALLOWED = {
    (StrategyState.OBSERVATION, Event.OPPORTUNITY): StrategyState.CANDIDATE,
    (StrategyState.CANDIDATE, Event.EVALUATED): StrategyState.EVALUATED,
    (StrategyState.CANDIDATE, Event.REJECTED): StrategyState.REJECTED,
    (StrategyState.CANDIDATE, Event.NO_TRADE): StrategyState.REJECTED,
    (StrategyState.EVALUATED, Event.AUTHORIZED): StrategyState.AUTHORIZED,
    (StrategyState.EVALUATED, Event.REJECTED): StrategyState.REJECTED,
    (StrategyState.AUTHORIZED, Event.ENTRY_INTENT): StrategyState.INTENT,
    (StrategyState.INTENT, Event.ORDER_SUBMITTED): StrategyState.ORDERED,
    (StrategyState.ORDERED, Event.PARTIAL_FILL): StrategyState.PARTIALLY_FILLED,
    (StrategyState.ORDERED, Event.FILL): StrategyState.OPEN,
    (StrategyState.ORDERED, Event.REJECTED): StrategyState.REJECTED,
    (StrategyState.ORDERED, Event.CANCELLED): StrategyState.REJECTED,
    (StrategyState.PARTIALLY_FILLED, Event.PARTIAL_FILL): StrategyState.PARTIALLY_FILLED,
    (StrategyState.PARTIALLY_FILLED, Event.FILL): StrategyState.OPEN,
    (StrategyState.PARTIALLY_FILLED, Event.CANCELLED): StrategyState.OPEN,
    (StrategyState.OPEN, Event.PROTECTION_UPDATED): StrategyState.PROTECTING,
    (StrategyState.PROTECTING, Event.PROTECTION_UPDATED): StrategyState.PROTECTING,
    (StrategyState.OPEN, Event.EXIT_INTENT): StrategyState.EXIT_INTENT,
    (StrategyState.PROTECTING, Event.EXIT_INTENT): StrategyState.EXIT_INTENT,
    (StrategyState.EXIT_INTENT, Event.EXIT_FILL): StrategyState.CLOSED,
    (StrategyState.EXIT_INTENT, Event.REJECTED): StrategyState.OPEN,
    (StrategyState.EXIT_INTENT, Event.CANCELLED): StrategyState.OPEN,
}


def transition(state: StrategyState, event: Event) -> StateTransition:
    try:
        current = _ALLOWED[(state, event)]
    except KeyError as exc:
        raise ValueError(f"invalid Adaptive Edge transition: {state} + {event}") from exc
    return StateTransition(state, event, current)
