"""A51 final holdout and claim-assembly primitives.

A51 protects a final untouched holdout from research-selection activity.
It records eligibility; it does not decide performance thresholds or make
financial claims.
"""
from __future__ import annotations

from dataclasses import dataclass


class FinalHoldoutError(ValueError):
    """Raised when an A51 invariant is violated."""


@dataclass(frozen=True)
class HoldoutCandidate:
    candidate_id: str
    evaluation_id: str
    result_fingerprint: str
    test_observed: bool
    selection_influenced: bool

    def __post_init__(self) -> None:
        for name in ("candidate_id", "evaluation_id", "result_fingerprint"):
            if not getattr(self, name).strip():
                raise FinalHoldoutError(f"{name} must not be empty")
        if self.test_observed or self.selection_influenced:
            raise FinalHoldoutError("final holdout candidate must not have prior test or selection influence")


@dataclass(frozen=True)
class FinalHoldoutEvidence:
    holdout_id: str
    evaluation_id: str
    candidate: HoldoutCandidate
    dataset_fingerprint: str
    claim_fingerprint: str

    def __post_init__(self) -> None:
        for name in ("holdout_id", "evaluation_id", "dataset_fingerprint", "claim_fingerprint"):
            if not getattr(self, name).strip():
                raise FinalHoldoutError(f"{name} must not be empty")
        if self.candidate.evaluation_id != self.evaluation_id:
            raise FinalHoldoutError("candidate and holdout evaluation identities must match")

    @classmethod
    def assemble(
        cls,
        holdout_id: str,
        evaluation_id: str,
        candidate: HoldoutCandidate,
        dataset_fingerprint: str,
        claim_fingerprint: str,
    ) -> "FinalHoldoutEvidence":
        return cls(holdout_id, evaluation_id, candidate, dataset_fingerprint, claim_fingerprint)
