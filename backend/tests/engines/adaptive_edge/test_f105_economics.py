from __future__ import annotations

import pytest

from app.engines.adaptive_edge.f105_economics import F105Candidate, evaluate_candidate


def test_f105_positive_conservative_ev_is_eligible() -> None:
    result = evaluate_candidate(
        F105Candidate(100.0, 120.0, 90.0, 0.75, 0.15, 0.10),
        execution_cost=1.0,
        sample_size=10_000,
    )
    assert result.eligible is True
    assert result.reason == "eligible"
    assert result.conservative_ev > 0


def test_f105_rejects_non_positive_conservative_ev() -> None:
    result = evaluate_candidate(
        F105Candidate(100.0, 105.0, 95.0, 0.45, 0.45, 0.10),
        execution_cost=1.0,
        sample_size=100,
    )
    assert result.eligible is False
    assert result.reason == "non_positive_conservative_ev"


def test_f105_fails_closed_for_insufficient_evidence() -> None:
    result = evaluate_candidate(
        F105Candidate(100.0, 120.0, 90.0, 0.8, 0.1, 0.1),
        execution_cost=1.0,
        sample_size=1,
    )
    assert result.eligible is False
    assert result.reason == "insufficient_evidence"


def test_f105_requires_real_execution_cost() -> None:
    with pytest.raises(ValueError, match="execution_cost"):
        evaluate_candidate(
            F105Candidate(100.0, 120.0, 90.0, 0.8, 0.1, 0.1),
            execution_cost=-1,
            sample_size=100,
        )


def test_f105_probabilities_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="probabilities"):
        evaluate_candidate(
            F105Candidate(100.0, 120.0, 90.0, 0.8, 0.3, 0.1),
            execution_cost=1.0,
            sample_size=100,
        )
