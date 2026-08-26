"""Explicit position lifecycle for Adaptive Edge.

Every state a position can be in, and every event that may move it, are named
here. Transitions not in the table raise, so an unhandled broker event stops
the position rather than leaving it in a state nobody chose. The states this
guards are the ones where an implicit fallthrough costs real money: an entry
that was rejected must not leave an open position behind, and an exit that was
rejected must not lose one.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StrategyState(str, Enum):
    OBSERVATION = "observation"
    CANDIDATE = "candidate"
    EVALUATED = "evaluated"
    AUTHORIZED = "authorized"
    INTENT = "intent"
    ORDERED = "ordered"
    PARTIALLY_FILLED = "partially_filled"
    OPEN = "open"
    EXIT_INTENT = "exit_intent"
    EXIT_ORDERED = "exit_ordered"
    CLOSED = "closed"
    REJECTED = "rejected"


class Event(str, Enum):
    OPPORTUNITY = "opportunity"
    EVALUATED = "evaluated"
    AUTHORIZED = "authorized"
    ENTRY_INTENT = "entry_intent"
    EXIT_INTENT = "exit_intent"
    ORDER_SUBMITTED = "order_submitted"
    PARTIAL_FILL = "partial_fill"
    FILL = "fill"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Transition:
    """The move that was made, kept whole so it can be logged as one record."""

    previous: StrategyState
    event: Event
    current: StrategyState


# Entry runs observation -> candidate -> evaluated -> authorized -> intent ->
# ordered -> open. Rejection before a fill ends at REJECTED, which is terminal
# and holds no position.
#
# Exit runs open -> exit_intent -> exit_ordered -> closed. Rejection anywhere on
# that path returns to OPEN, because a refused exit order means the position is
# still there — treating it as closed would silently abandon a live position.
_TRANSITIONS: dict[tuple[StrategyState, Event], StrategyState] = {
    (StrategyState.OBSERVATION, Event.OPPORTUNITY): StrategyState.CANDIDATE,
    (StrategyState.CANDIDATE, Event.EVALUATED): StrategyState.EVALUATED,
    (StrategyState.CANDIDATE, Event.REJECTED): StrategyState.REJECTED,
    (StrategyState.EVALUATED, Event.AUTHORIZED): StrategyState.AUTHORIZED,
    (StrategyState.EVALUATED, Event.REJECTED): StrategyState.REJECTED,
    (StrategyState.AUTHORIZED, Event.ENTRY_INTENT): StrategyState.INTENT,
    (StrategyState.AUTHORIZED, Event.REJECTED): StrategyState.REJECTED,
    (StrategyState.INTENT, Event.ORDER_SUBMITTED): StrategyState.ORDERED,
    (StrategyState.INTENT, Event.REJECTED): StrategyState.REJECTED,
    (StrategyState.INTENT, Event.CANCELLED): StrategyState.REJECTED,
    (StrategyState.ORDERED, Event.PARTIAL_FILL): StrategyState.PARTIALLY_FILLED,
    (StrategyState.ORDERED, Event.FILL): StrategyState.OPEN,
    (StrategyState.ORDERED, Event.REJECTED): StrategyState.REJECTED,
    (StrategyState.ORDERED, Event.CANCELLED): StrategyState.REJECTED,
    # A partially filled entry already holds quantity, so neither a rejection
    # nor a cancellation of the remainder may discard it.
    (StrategyState.PARTIALLY_FILLED, Event.PARTIAL_FILL): StrategyState.PARTIALLY_FILLED,
    (StrategyState.PARTIALLY_FILLED, Event.FILL): StrategyState.OPEN,
    (StrategyState.PARTIALLY_FILLED, Event.REJECTED): StrategyState.OPEN,
    (StrategyState.PARTIALLY_FILLED, Event.CANCELLED): StrategyState.OPEN,
    (StrategyState.OPEN, Event.EXIT_INTENT): StrategyState.EXIT_INTENT,
    (StrategyState.EXIT_INTENT, Event.ORDER_SUBMITTED): StrategyState.EXIT_ORDERED,
    (StrategyState.EXIT_INTENT, Event.REJECTED): StrategyState.OPEN,
    (StrategyState.EXIT_INTENT, Event.CANCELLED): StrategyState.OPEN,
    (StrategyState.EXIT_ORDERED, Event.PARTIAL_FILL): StrategyState.EXIT_ORDERED,
    (StrategyState.EXIT_ORDERED, Event.FILL): StrategyState.CLOSED,
    (StrategyState.EXIT_ORDERED, Event.REJECTED): StrategyState.OPEN,
    (StrategyState.EXIT_ORDERED, Event.CANCELLED): StrategyState.OPEN,
}

TERMINAL_STATES = frozenset({StrategyState.CLOSED, StrategyState.REJECTED})


def transition(state: StrategyState, event: Event) -> Transition:
    """Apply `event` to `state`, or refuse.

    Refusing is the point: an event that is not in the table is one this
    lifecycle has no defined answer for, and guessing an answer is how a
    position ends up in a state no one designed.
    """
    try:
        target = _TRANSITIONS[(state, event)]
    except KeyError:
        raise ValueError(
            f"invalid transition: {state.value} cannot handle {event.value}"
        ) from None
    return Transition(previous=state, event=event, current=target)
