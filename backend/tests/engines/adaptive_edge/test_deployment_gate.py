import pytest

from app.engines.adaptive_edge.deployment_gate import (
    DeploymentGateError,
    GateStatus,
    assemble_deployment_readiness,
)
from app.engines.adaptive_edge.final_holdout import FinalHoldoutEvidence, HoldoutCandidate
from app.engines.adaptive_edge.claim_statistics import CorrectionStatus, StatisticalValidityContract
from app.engines.adaptive_edge.promotion_boundary import PromotionDecision, assemble_promotion_eligibility


def evidence():
    candidate = HoldoutCandidate("candidate-1", "eval-1", "result-1", False, False)
    holdout = FinalHoldoutEvidence.assemble("holdout-1", "eval-1", candidate, "dataset-1", "claim-1")
    stats = StatisticalValidityContract(
        "eval-1", "registry-1", 10, CorrectionStatus.APPLIED,
        correction_method_id="method-1", adjusted_claim=True,
    )
    return assemble_promotion_eligibility(holdout, stats)


def decision(outcome="approved"):
    return PromotionDecision("decision-1", "eval-1", "policy-1", "1", outcome, "explicit policy decision")


def test_deployment_gate_is_not_live_authorized_by_default():
    readiness = assemble_deployment_readiness(
        evidence(), decision(), operational_evidence_id=None,
        gate_policy_id="gate-1", gate_policy_version="1",
    )
    assert readiness.status is GateStatus.BLOCKED
    assert not readiness.live_trading_authorized


def test_live_authorization_requires_operational_evidence():
    with pytest.raises(DeploymentGateError):
        assemble_deployment_readiness(
            evidence(), decision(), operational_evidence_id=None,
            gate_policy_id="gate-1", gate_policy_version="1",
            status=GateStatus.AUTHORIZED, live_authorization_id="auth-1",
        )


def test_live_authorization_requires_approved_promotion():
    with pytest.raises(DeploymentGateError):
        assemble_deployment_readiness(
            evidence(), decision("deferred"), operational_evidence_id="ops-1",
            gate_policy_id="gate-1", gate_policy_version="1",
            status=GateStatus.AUTHORIZED, live_authorization_id="auth-1",
        )


def test_authorized_state_requires_authorization_identity():
    with pytest.raises(DeploymentGateError):
        assemble_deployment_readiness(
            evidence(), decision(), operational_evidence_id="ops-1",
            gate_policy_id="gate-1", gate_policy_version="1",
            status=GateStatus.AUTHORIZED,
        )


def test_ready_state_cannot_carry_live_authorization():
    with pytest.raises(DeploymentGateError):
        assemble_deployment_readiness(
            evidence(), decision(), operational_evidence_id="ops-1",
            gate_policy_id="gate-1", gate_policy_version="1",
            status=GateStatus.READY, live_authorization_id="auth-1",
        )
