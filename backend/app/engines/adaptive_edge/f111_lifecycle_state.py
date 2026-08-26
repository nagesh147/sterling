"""F-111 research lifecycle state machine.

This module implements the recovered state-transition boundary without
inventing the unresolved production F-111 scoring parameters.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LifecycleState(str, Enum):
    OPEN = "OPEN"
    PROTECTED = "PROTECTED"
    EXIT_PENDING = "EXIT_PENDING"
    CLOSED = "CLOSED"


class LifecycleAction(str, Enum):
    HOLD = "HOLD"
    PROTECT = "PROTECT"
    EXIT = "EXIT"


@dataclass(frozen=True)
class LifecycleInput:
    position_quantity: int
    continuation_value: float | None
    protection_hit: bool
    emergency_reversal: bool
    session_cutoff: bool


@dataclass(frozen=True)
class LifecycleDecision:
    previous_state: LifecycleState
    next_state: LifecycleState
    action: LifecycleAction
    reason: str


class F111LifecycleStateMachine:
    """Deterministic, fail-closed F-111 transition boundary."""

    def __init__(self, initial_state: LifecycleState = LifecycleState.OPEN) -> None:
        self.state = initial_state

    def evaluate(self, event: LifecycleInput) -> LifecycleDecision:
        previous = self.state
        if event.position_quantity < 0:
            raise ValueError("position_quantity must be non-negative")

        if previous is LifecycleState.CLOSED:
            if event.position_quantity != 0:
                raise ValueError("closed lifecycle cannot carry an open position")
            return LifecycleDecision(previous, previous, LifecycleAction.HOLD, "already_closed")

        if event.position_quantity == 0:
            self.state = LifecycleState.CLOSED
            return LifecycleDecision(previous, self.state, LifecycleAction.EXIT, "position_flat")

        if event.protection_hit:
            self.state = LifecycleState.EXIT_PENDING
            return LifecycleDecision(previous, self.state, LifecycleAction.EXIT, "protection_authority")

        if event.emergency_reversal:
            self.state = LifecycleState.EXIT_PENDING
            return LifecycleDecision(previous, self.state, LifecycleAction.EXIT, "emergency_reversal")

        if event.session_cutoff:
            self.state = LifecycleState.EXIT_PENDING
            return LifecycleDecision(previous, self.state, LifecycleAction.EXIT, "session_cutoff")

        if event.continuation_value is None:
            raise ValueError("missing continuation_value: F-111 fails closed")

        if event.continuation_value <= 0:
            self.state = LifecycleState.EXIT_PENDING
            return LifecycleDecision(previous, self.state, LifecycleAction.EXIT, "continuation_value_non_positive")

        if event.protection_hit is False and previous is LifecycleState.OPEN:
            self.state = LifecycleState.PROTECTED
            return LifecycleDecision(previous, self.state, LifecycleAction.PROTECT, "position_protected")

        return LifecycleDecision(previous, previous, LifecycleAction.HOLD, "continuation_positive")
