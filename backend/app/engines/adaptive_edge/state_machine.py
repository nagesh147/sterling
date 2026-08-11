"""Adaptive Edge orchestration state machine.

This module models lifecycle state only. It does not create broker orders or
infer fills. Broker/execution truth remains downstream of the strategy intent.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class StrategyState(str, Enum):
    FLAT = "FLAT"
    CANDIDATE = "CANDIDATE"
    AUTHORIZED = "AUTHORIZED"
    ENTRY_PENDING = "ENTRY_PENDING"
    OPEN = "OPEN"
    PROTECTED = "PROTECTED"
    EXIT_PENDING = "EXIT_PENDING"
    CLOSED = "CLOSED"


class Event(str, Enum):
    OPPORTUNITY = "OPPORTUNITY"
    NO_TRADE = "NO_TRADE"
    AUTHORIZED = "AUTHORIZED"
    ENTRY_INTENT = "ENTRY_INTENT"
    FILL = "FILL"
    PROTECTION_UPDATED = "PROTECTION_UPDATED"
    EXIT_INTENT = "EXIT_INTENT"
    EXIT_FILL = "EXIT_FILL"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class StateTransition:
    previous: StrategyState
    event: Event
    current: StrategyState


_ALLOWED = {
    (StrategyState.FLAT, Event.OPPORTUNITY): StrategyState.CANDIDATE,
    (StrategyState.CANDIDATE, Event.AUTHORIZED): StrategyState.AUTHORIZED,
    (StrategyState.CANDIDATE, Event.NO_TRADE): StrategyState.FLAT,
    (StrategyState.AUTHORIZED, Event.ENTRY_INTENT): StrategyState.ENTRY_PENDING,
    (StrategyState.ENTRY_PENDING, Event.FILL): StrategyState.OPEN,
    (StrategyState.ENTRY_PENDING, Event.REJECTED): StrategyState.FLAT,
    (StrategyState.ENTRY_PENDING, Event.CANCELLED): StrategyState.FLAT,
    (StrategyState.OPEN, Event.PROTECTION_UPDATED): StrategyState.PROTECTED,
    (StrategyState.PROTECTED, Event.PROTECTION_UPDATED): StrategyState.PROTECTED,
    (StrategyState.OPEN, Event.EXIT_INTENT): StrategyState.EXIT_PENDING,
    (StrategyState.PROTECTED, Event.EXIT_INTENT): StrategyState.EXIT_PENDING,
    (StrategyState.EXIT_PENDING, Event.EXIT_FILL): StrategyState.CLOSED,
    (StrategyState.EXIT_PENDING, Event.REJECTED): StrategyState.OPEN,
    (StrategyState.EXIT_PENDING, Event.CANCELLED): StrategyState.OPEN,
}


def transition(state: StrategyState, event: Event) -> StateTransition:
    try:
        current = _ALLOWED[(state, event)]
    except KeyError as exc:
        raise ValueError(f"invalid Adaptive Edge transition: {state} + {event}") from exc
    return StateTransition(state, event, current)
