from dataclasses import replace

import pytest

from app.engines.adaptive_edge.oos_claims import (
    ClaimStatus,
    EvaluationEvidence,
    OOSClaimError,
    TestUseEvent,
    assess_claim,
    reconstitute_final_holdout,
)


def evidence() -> EvaluationEvidence:
    return EvaluationEvidence(
        evaluation_id="eval-1",
        candidate_id="candidate-1",
        code_version="code-1",
        feature_version="feature-1",
        label_version="label-1",
        execution_version="execution-1",
        boundary_id="test-1",
        result_fingerprint="result-1",
    )


def test_untouched_evaluation_is_claim_eligible():
    claim = assess_claim(evidence(), claim_id="claim-1")
    assert claim.status is ClaimStatus.ELIGIBLE
    assert claim.contamination_event_ids == ()


def test_test_use_contaminates_claim():
    event = TestUseEvent(
        evaluation_id="eval-1",
        event_id="use-1",
        purpose="candidate selection",
        affected_candidate_ids=("candidate-2",),
    )
    claim = assess_claim(evidence(), test_use_events=(event,), claim_id="claim-1")
    assert claim.status is ClaimStatus.CONTAMINATED
    assert claim.contamination_event_ids == ("use-1",)


def test_unrelated_test_use_does_not_contaminate_evaluation():
    event = TestUseEvent(
        evaluation_id="other-eval",
        event_id="use-1",
        purpose="research",
        affected_candidate_ids=("candidate-2",),
    )
    claim = assess_claim(evidence(), test_use_events=(event,), claim_id="claim-1")
    assert claim.status is ClaimStatus.ELIGIBLE


def test_reconstituted_claim_requires_new_boundary():
    claim = reconstitute_final_holdout(
        evidence(), replacement_boundary_id="test-2", claim_id="claim-2"
    )
    assert claim.status is ClaimStatus.RECONSTITUTED


def test_reconstitution_cannot_reuse_contaminated_boundary():
    with pytest.raises(OOSClaimError, match="replacement boundary"):
        reconstitute_final_holdout(
            evidence(), replacement_boundary_id="test-1", claim_id="claim-2"
        )


def test_contaminated_claim_requires_event_identity():
    with pytest.raises(OOSClaimError, match="contamination events"):
        from app.engines.adaptive_edge.oos_claims import OOSClaim
        OOSClaim(
            claim_id="claim-1",
            evaluation_id="eval-1",
            status=ClaimStatus.CONTAMINATED,
            evidence_id="eval-1",
        )
