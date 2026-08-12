"""A53 claim/promotion boundary primitives.

A53 separates evidence validity from a deployment/promotion decision. It
requires upstream A51/A52 eligibility and preserves the policy identity that
made the decision. It does not invent a promotion threshold or trading rule.
"""
from __future__ import annotations

from dataclasses import dataclass

from .claim_statistics import StatisticalValidityContract
from .final_holdout import FinalHoldoutEvidence


class PromotionBoundaryError(ValueError):
    """Raised when an A53 invariant is violated."""


@dataclass(frozen=True)
class PromotionDecision:
    decision_id: str
    evaluation_id: str
    policy_id: str
    policy_version: str
    outcome: str
    rationale: str

    def __post_init__(self) -> None:
        for name in ("decision_id", "evaluation_id", "policy_id", "policy_version", "outcome", "rationale"):
            if not getattr(self, name).strip():
                raise PromotionBoundaryError(f"{name} must not be empty")
        if self.outcome not in {"approved", "rejected", "deferred"}:
            raise PromotionBoundaryError("outcome must be approved, rejected, or deferred")


@dataclass(frozen=True)
class PromotionEligibility:
    evaluation_id: str
    holdout: FinalHoldoutEvidence
    statistics: StatisticalValidityContract

    def __post_init__(self) -> None:
        if self.holdout.evaluation_id != self.evaluation_id or self.statistics.evaluation_id != self.evaluation_id:
            raise PromotionBoundaryError("all upstream evidence must share evaluation_id")

    def eligible_for_policy_decision(self) -> bool:
        return self.statistics.claim_eligible()


def assemble_promotion_eligibility(
    holdout: FinalHoldoutEvidence,
    statistics: StatisticalValidityContract,
) -> PromotionEligibility:
    if not statistics.claim_eligible():
        raise PromotionBoundaryError("statistically valid adjusted claim is required before promotion decision")
    return PromotionEligibility(
        evaluation_id=holdout.evaluation_id,
        holdout=holdout,
        statistics=statistics,
    )
