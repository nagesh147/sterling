"""A47 out-of-sample evaluation and claim-protection primitives.

A47 records how an evaluation result was produced and whether it remains
eligible for an untouched out-of-sample claim. It does not define performance
metrics, statistical thresholds, target horizons, or promotion policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class OOSClaimError(ValueError):
    """Raised when an A47 invariant is violated."""


class ClaimStatus(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    ELIGIBLE = "ELIGIBLE"
    CONTAMINATED = "CONTAMINATED"
    RECONSTITUTED = "RECONSTITUTED"
    INSUFFICIENT_LINEAGE = "INSUFFICIENT_LINEAGE"


@dataclass(frozen=True)
class EvaluationEvidence:
    evaluation_id: str
    candidate_id: str
    code_version: str
    feature_version: str
    label_version: str
    execution_version: str
    boundary_id: str
    result_fingerprint: str
    metrics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "evaluation_id",
            "candidate_id",
            "code_version",
            "feature_version",
            "label_version",
            "execution_version",
            "boundary_id",
            "result_fingerprint",
        ):
            if not getattr(self, name).strip():
                raise OOSClaimError(f"{name} must not be empty")


@dataclass(frozen=True)
class TestUseEvent:
    evaluation_id: str
    event_id: str
    purpose: str
    affected_candidate_ids: tuple[str, ...]

    __test__ = False

    def __post_init__(self) -> None:
        if not self.evaluation_id.strip() or not self.event_id.strip():
            raise OOSClaimError("test-use identity is required")
        if not self.purpose.strip():
            raise OOSClaimError("test-use purpose is required")
        if not self.affected_candidate_ids:
            raise OOSClaimError("test use must identify affected candidates")


@dataclass(frozen=True)
class OOSClaim:
    claim_id: str
    evaluation_id: str
    status: ClaimStatus
    evidence_id: str
    contamination_event_ids: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.evaluation_id.strip():
            raise OOSClaimError("claim identity is required")
        if not self.evidence_id.strip():
            raise OOSClaimError("evidence_id is required")
        if self.status == ClaimStatus.CONTAMINATED and not self.contamination_event_ids:
            raise OOSClaimError("contaminated claims require contamination events")


def assess_claim(
    evidence: EvaluationEvidence,
    *,
    test_use_events: Iterable[TestUseEvent] = (),
    claim_id: str,
) -> OOSClaim:
    """Determine claim eligibility from recorded test-use history only."""
    if not claim_id.strip():
        raise OOSClaimError("claim_id must not be empty")
    events = tuple(test_use_events)
    relevant = tuple(event for event in events if event.evaluation_id == evidence.evaluation_id)
    if relevant:
        return OOSClaim(
            claim_id=claim_id,
            evaluation_id=evidence.evaluation_id,
            status=ClaimStatus.CONTAMINATED,
            evidence_id=evidence.evaluation_id,
            contamination_event_ids=tuple(event.event_id for event in relevant),
            reason="test results influenced or were inspected during research",
        )
    return OOSClaim(
        claim_id=claim_id,
        evaluation_id=evidence.evaluation_id,
        status=ClaimStatus.ELIGIBLE,
        evidence_id=evidence.evaluation_id,
    )


def reconstitute_final_holdout(
    evidence: EvaluationEvidence,
    *,
    replacement_boundary_id: str,
    claim_id: str,
) -> OOSClaim:
    """Create a reconstituted claim only after replacing a contaminated boundary."""
    if not replacement_boundary_id.strip():
        raise OOSClaimError("replacement boundary is required")
    if replacement_boundary_id == evidence.boundary_id:
        raise OOSClaimError("replacement boundary must differ from contaminated boundary")
    if not claim_id.strip():
        raise OOSClaimError("claim_id must not be empty")
    return OOSClaim(
        claim_id=claim_id,
        evaluation_id=evidence.evaluation_id,
        status=ClaimStatus.RECONSTITUTED,
        evidence_id=evidence.evaluation_id,
        reason=f"replacement boundary required: {replacement_boundary_id}",
    )
