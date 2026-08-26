import pytest

from backend.app.engines.adaptive_edge.claim_statistics import CorrectionStatus, StatisticalValidityContract
from backend.app.engines.adaptive_edge.final_holdout import FinalHoldoutEvidence, HoldoutCandidate
from backend.app.engines.adaptive_edge.promotion_boundary import (
    PromotionBoundaryError,
    assemble_promotion_eligibility,
)


def holdout():
    candidate = HoldoutCandidate("candidate-1", "eval-1", "result-1", False, False)
    return FinalHoldoutEvidence.assemble("holdout-1", "eval-1", candidate, "dataset-1", "claim-1")


def stats(applied: bool):
    return StatisticalValidityContract(
        evaluation_id="eval-1",
        research_registry_fingerprint="registry-1",
        candidate_population_size=10,
        correction_status=CorrectionStatus.APPLIED if applied else CorrectionStatus.UNRESOLVED,
        correction_method_id="method-1" if applied else None,
        adjusted_claim=applied,
    )


def test_promotion_eligibility_requires_validated_upstream_claim():
    eligibility = assemble_promotion_eligibility(holdout(), stats(True))
    assert eligibility.eligible_for_policy_decision()


def test_promotion_eligibility_rejects_unresolved_statistics():
    with pytest.raises(PromotionBoundaryError):
        assemble_promotion_eligibility(holdout(), stats(False))


def test_promotion_eligibility_rejects_mismatched_evaluation():
    candidate = HoldoutCandidate("candidate-1", "eval-2", "result-1", False, False)
    evidence = FinalHoldoutEvidence.assemble("holdout-1", "eval-2", candidate, "dataset-1", "claim-1")
    with pytest.raises(PromotionBoundaryError):
        assemble_promotion_eligibility(evidence, stats(True))
