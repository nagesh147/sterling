"""Research implementation of the V1.0 position-management exit gate."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExitDecision(str, Enum):
    HOLD = "HOLD"
    UPDATE_STOP = "UPDATE_STOP"
    EXIT = "EXIT"


@dataclass(frozen=True)
class F111State:
    protective_condition_breached: bool
    conservative_continuation_value: float | None
    emergency_reversal: bool
    session_termination: bool
    stop_improved: bool


def evaluate_exit(state: F111State) -> ExitDecision:
    if state.protective_condition_breached or state.session_termination:
        return ExitDecision.EXIT
    if state.emergency_reversal and (
        state.conservative_continuation_value is None
        or state.conservative_continuation_value <= 0
    ):
        return ExitDecision.EXIT
    if state.conservative_continuation_value is not None and state.conservative_continuation_value <= 0:
        return ExitDecision.EXIT
    if state.stop_improved:
        return ExitDecision.UPDATE_STOP
    return ExitDecision.HOLD
