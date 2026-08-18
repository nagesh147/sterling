from __future__ import annotations

import pytest

from app.engines.adaptive_edge.f114_portfolio_boundary import (
    F114Admission,
    PortfolioAssessment,
    PortfolioDecision,
    admit_candidate,
)


def assessment(decision: PortfolioDecision, quantity: int = 50) -> PortfolioAssessment:
    return PortfolioAssessment(
        decision=decision,
        assessment_id="pa-001",
        model_version="unresolved-portfolio-v0",
        causal_cutoff="2026-08-18T09:30:00Z",
        reason="test",
        approved_quantity=quantity if decision in (PortfolioDecision.ADMIT, PortfolioDecision.REDUCE) else 0,
    )


def test_f114_requires_portfolio_assessment() -> None:
    result = admit_candidate(
        candidate_quantity=25,
        standalone_eligible=True,
        execution_authorized=True,
        portfolio_assessment=None,
    )
    assert result == F114Admission(False, 0, "portfolio_assessment_unavailable")


def test_f114_rejects_when_portfolio_rejects() -> None:
    result = admit_candidate(
        candidate_quantity=25,
        standalone_eligible=True,
        execution_authorized=True,
        portfolio_assessment=assessment(PortfolioDecision.REJECT),
    )
    assert result.admitted is False
    assert result.reason == "portfolio_rejected"


def test_f114_can_only_reduce_candidate_quantity() -> None:
    result = admit_candidate(
        candidate_quantity=100,
        standalone_eligible=True,
        execution_authorized=True,
        portfolio_assessment=assessment(PortfolioDecision.REDUCE, 50),
    )
    assert result.admitted is True
    assert result.quantity == 50


def test_f114_never_increases_candidate_quantity() -> None:
    result = admit_candidate(
        candidate_quantity=25,
        standalone_eligible=True,
        execution_authorized=True,
        portfolio_assessment=assessment(PortfolioDecision.ADMIT, 100),
    )
    assert result.quantity == 25


def test_f114_requires_upstream_eligibility_and_authorization() -> None:
    pa = assessment(PortfolioDecision.ADMIT)
    assert admit_candidate(candidate_quantity=25, standalone_eligible=False, execution_authorized=True, portfolio_assessment=pa).admitted is False
    assert admit_candidate(candidate_quantity=25, standalone_eligible=True, execution_authorized=False, portfolio_assessment=pa).admitted is False


def test_f114_assessment_metadata_is_required() -> None:
    with pytest.raises(ValueError):
        PortfolioAssessment(PortfolioDecision.ADMIT, "", "v0", "t", "test", 25)
