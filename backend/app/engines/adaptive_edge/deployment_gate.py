"""A54 production-readiness and deployment authorization boundary.

A54 separates research promotion from operational readiness and live
authorization. It records gate state without inventing trading thresholds,
risk limits, or deployment policy values.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .promotion_boundary import PromotionDecision, PromotionEligibility


class DeploymentGateError(ValueError):
    """Raised when an A54 deployment-gate invariant is violated."""


class GateStatus(str, Enum):
    BLOCKED = "blocked"
    READY = "ready"
    AUTHORIZED = "authorized"


@dataclass(frozen=True)
class DeploymentReadiness:
    evaluation_id: str
    promotion: PromotionEligibility
    decision: PromotionDecision
    operational_evidence_id: str | None
    gate_policy_id: str
    gate_policy_version: str
    status: GateStatus
    live_authorization_id: str | None = None

    def __post_init__(self) -> None:
        if not self.evaluation_id.strip():
            raise DeploymentGateError("evaluation_id must not be empty")
        if self.promotion.evaluation_id != self.evaluation_id:
            raise DeploymentGateError("promotion evidence must match evaluation_id")
        if self.decision.evaluation_id != self.evaluation_id:
            raise DeploymentGateError("promotion decision must match evaluation_id")
        if not self.gate_policy_id.strip() or not self.gate_policy_version.strip():
            raise DeploymentGateError("gate policy identity is required")
        if self.status is GateStatus.AUTHORIZED:
            if self.decision.outcome != "approved":
                raise DeploymentGateError("live authorization requires an approved promotion decision")
            if not self.operational_evidence_id:
                raise DeploymentGateError("live authorization requires operational evidence")
            if not self.live_authorization_id:
                raise DeploymentGateError("authorized state requires live_authorization_id")
        elif self.live_authorization_id is not None:
            raise DeploymentGateError("live authorization identity is only valid in authorized state")

    @property
    def live_trading_authorized(self) -> bool:
        return self.status is GateStatus.AUTHORIZED


def assemble_deployment_readiness(
    promotion: PromotionEligibility,
    decision: PromotionDecision,
    *,
    operational_evidence_id: str | None,
    gate_policy_id: str,
    gate_policy_version: str,
    status: GateStatus = GateStatus.BLOCKED,
    live_authorization_id: str | None = None,
) -> DeploymentReadiness:
    return DeploymentReadiness(
        evaluation_id=promotion.evaluation_id,
        promotion=promotion,
        decision=decision,
        operational_evidence_id=operational_evidence_id,
        gate_policy_id=gate_policy_id,
        gate_policy_version=gate_policy_version,
        status=status,
        live_authorization_id=live_authorization_id,
    )
