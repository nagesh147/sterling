"""A55 operational controls and incident boundary.

The contract records runtime observations and explicit safety outcomes. It
intentionally does not invent provider-specific thresholds or trading policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperationalControlError(ValueError):
    """Raised when an A55 invariant is violated."""


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class SafetyAction(str, Enum):
    CONTINUE = "continue"
    DEGRADE = "degrade"
    BLOCK_NEW = "block_new"
    HALT = "halt"


@dataclass(frozen=True)
class OperationalObservation:
    observation_id: str
    component: str
    observed_at_ms: int
    health: HealthState
    evidence_id: str

    def __post_init__(self) -> None:
        if not self.observation_id.strip() or not self.component.strip():
            raise OperationalControlError("observation identity and component are required")
        if self.observed_at_ms < 0:
            raise OperationalControlError("observed_at_ms must be non-negative")
        if not self.evidence_id.strip():
            raise OperationalControlError("evidence_id is required")


@dataclass(frozen=True)
class OperationalControlDecision:
    decision_id: str
    observation_id: str
    action: SafetyAction
    policy_id: str
    policy_version: str
    rationale: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.decision_id, "decision_id"),
            (self.observation_id, "observation_id"),
            (self.policy_id, "policy_id"),
            (self.policy_version, "policy_version"),
            (self.rationale, "rationale"),
        ):
            if not value.strip():
                raise OperationalControlError(f"{name} must not be empty")


def apply_operational_control(
    observation: OperationalObservation,
    decision: OperationalControlDecision,
) -> OperationalControlDecision:
    if decision.observation_id != observation.observation_id:
        raise OperationalControlError("decision must reference the observed incident/health event")
    return decision
