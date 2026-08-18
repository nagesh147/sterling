"""F-114 portfolio admission boundary.

This module deliberately does not invent a portfolio-risk aggregation formula.
It defines the architectural boundary and requires an externally resolved,
versioned portfolio assessment before admitting a candidate.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PortfolioDecision(str, Enum):
    ADMIT = "ADMIT"
    REDUCE = "REDUCE"
    REJECT = "REJECT"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class PortfolioAssessment:
    decision: PortfolioDecision
    assessment_id: str
    model_version: str
    causal_cutoff: str
    reason: str
    approved_quantity: int = 0

    def __post_init__(self) -> None:
        if not self.assessment_id.strip():
            raise ValueError("assessment_id is required")
        if not self.model_version.strip():
            raise ValueError("model_version is required")
        if not self.causal_cutoff.strip():
            raise ValueError("causal_cutoff is required")
        if self.approved_quantity < 0:
            raise ValueError("approved_quantity cannot be negative")
        if self.decision == PortfolioDecision.ADMIT and self.approved_quantity <= 0:
            raise ValueError("ADMIT requires positive approved_quantity")
        if self.decision != PortfolioDecision.ADMIT and self.approved_quantity != 0:
            raise ValueError("non-ADMIT portfolio decisions cannot approve quantity")


@dataclass(frozen=True)
class F114Admission:
    admitted: bool
    quantity: int
    reason: str
    assessment_id: str | None = None


def admit_candidate(
    *,
    candidate_quantity: int,
    standalone_eligible: bool,
    execution_authorized: bool,
    portfolio_assessment: PortfolioAssessment | None,
) -> F114Admission:
    """Apply the F-114 architectural gate without defining portfolio math."""
    if candidate_quantity <= 0:
        return F114Admission(False, 0, "invalid_candidate_quantity")
    if not standalone_eligible:
        return F114Admission(False, 0, "standalone_ineligible")
    if not execution_authorized:
        return F114Admission(False, 0, "execution_not_authorized")
    if portfolio_assessment is None:
        return F114Admission(False, 0, "portfolio_assessment_unavailable")
    if portfolio_assessment.decision == PortfolioDecision.REJECT:
        return F114Admission(False, 0, "portfolio_rejected", portfolio_assessment.assessment_id)
    if portfolio_assessment.decision == PortfolioDecision.UNAVAILABLE:
        return F114Admission(False, 0, "portfolio_assessment_unavailable", portfolio_assessment.assessment_id)
    if portfolio_assessment.decision == PortfolioDecision.REDUCE:
        quantity = min(candidate_quantity, portfolio_assessment.approved_quantity)
        if quantity <= 0:
            return F114Admission(False, 0, "portfolio_reduced_to_zero", portfolio_assessment.assessment_id)
        return F114Admission(True, quantity, "portfolio_reduced", portfolio_assessment.assessment_id)
    return F114Admission(True, min(candidate_quantity, portfolio_assessment.approved_quantity), "portfolio_admitted", portfolio_assessment.assessment_id)
