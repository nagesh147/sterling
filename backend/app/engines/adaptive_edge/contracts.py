"""Strategy-specific contracts for Adaptive Edge.

Important: DynamicMode and DynamicRisk are intentionally separate state axes.
A mode transition can never mutate previously authorized risk by implication.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DynamicMode(str, Enum):
    """Strategy operating mode. This describes behaviour, not risk capacity."""

    OBSERVE = "observe"
    ACTIVE = "active"
    INTRADAY = "intraday"
    DEFENSIVE = "defensive"
    EXIT_ONLY = "exit_only"
    HALTED = "halted"


class RiskState(str, Enum):
    """Independent risk authorization state."""

    UNAUTHORIZED = "unauthorized"
    AUTHORIZED = "authorized"
    REDUCED = "reduced"
    FROZEN = "frozen"
    HALTED = "halted"


class OpportunityState(str, Enum):
    NONE = "none"
    DETECTED = "detected"
    VALIDATED = "validated"
    EXECUTABLE = "executable"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass(frozen=True)
class RiskAuthorization:
    """Immutable risk authorization attached to one opportunity.

    `authorized_risk` is the ceiling already granted. Changing strategy mode,
    mark-to-market P&L, or prediction state cannot mutate this object.
    """

    opportunity_id: str
    authorized_risk: float
    risk_state: RiskState
    policy_version: str
    issued_at: str


@dataclass(frozen=True)
class AdaptiveEdgeState:
    """Minimal engine state; richer fields are added only when specified."""

    mode: DynamicMode = DynamicMode.OBSERVE
    risk_state: RiskState = RiskState.UNAUTHORIZED
    opportunity_state: OpportunityState = OpportunityState.NONE
    authorization: Optional[RiskAuthorization] = None

    def with_mode(self, mode: DynamicMode) -> "AdaptiveEdgeState":
        """Change operating mode without changing risk authorization."""
        return AdaptiveEdgeState(
            mode=mode,
            risk_state=self.risk_state,
            opportunity_state=self.opportunity_state,
            authorization=self.authorization,
        )
