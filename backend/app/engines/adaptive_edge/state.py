"""Deterministic state transitions for Adaptive Edge.

This module deliberately does not calculate risk from mode. Risk authorization
is an independent object and can only be replaced by an explicit risk action.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .contracts import AdaptiveEdgeState, DynamicMode, OpportunityState, RiskState


class StateTransitionError(ValueError):
    """Raised when a requested engine transition violates its state contract."""


class StateEvent(str, Enum):
    OPPORTUNITY_DETECTED = "opportunity_detected"
    OPPORTUNITY_VALIDATED = "opportunity_validated"
    OPPORTUNITY_REJECTED = "opportunity_rejected"
    OPPORTUNITY_EXPIRED = "opportunity_expired"
    ACTIVATE = "activate"
    ENTER_INTRADAY = "enter_intraday"
    DEFENSIVE = "defensive"
    EXIT_ONLY = "exit_only"
    HALT = "halt"
    OBSERVE = "observe"


@dataclass(frozen=True)
class StateTransition:
    event: StateEvent
    resulting_state: AdaptiveEdgeState


def transition(state: AdaptiveEdgeState, event: StateEvent) -> StateTransition:
    """Apply one explicitly permitted strategy-state transition.

    Notice that no transition in this function increases risk authorization.
    `HALT` freezes risk; mode changes preserve the existing authorization object.
    """
    if event is StateEvent.HALT:
        next_state = AdaptiveEdgeState(
            mode=DynamicMode.HALTED,
            risk_state=RiskState.HALTED,
            opportunity_state=state.opportunity_state,
            authorization=state.authorization,
        )
        return StateTransition(event, next_state)

    if state.mode is DynamicMode.HALTED:
        if event is not StateEvent.OBSERVE:
            raise StateTransitionError("halted engine cannot enter an active mode")
        next_state = AdaptiveEdgeState(
            mode=DynamicMode.OBSERVE,
            risk_state=state.risk_state,
            opportunity_state=state.opportunity_state,
            authorization=state.authorization,
        )
        return StateTransition(event, next_state)

    mode_map = {
        StateEvent.ACTIVATE: DynamicMode.ACTIVE,
        StateEvent.ENTER_INTRADAY: DynamicMode.INTRADAY,
        StateEvent.DEFENSIVE: DynamicMode.DEFENSIVE,
        StateEvent.EXIT_ONLY: DynamicMode.EXIT_ONLY,
        StateEvent.OBSERVE: DynamicMode.OBSERVE,
    }
    if event in mode_map:
        return StateTransition(event, state.with_mode(mode_map[event]))

    opportunity_map = {
        StateEvent.OPPORTUNITY_DETECTED: OpportunityState.DETECTED,
        StateEvent.OPPORTUNITY_VALIDATED: OpportunityState.VALIDATED,
        StateEvent.OPPORTUNITY_REJECTED: OpportunityState.REJECTED,
        StateEvent.OPPORTUNITY_EXPIRED: OpportunityState.EXPIRED,
    }
    if event in opportunity_map:
        next_state = AdaptiveEdgeState(
            mode=state.mode,
            risk_state=state.risk_state,
            opportunity_state=opportunity_map[event],
            authorization=state.authorization,
        )
        return StateTransition(event, next_state)

    raise StateTransitionError(f"unsupported state event: {event.value}")
