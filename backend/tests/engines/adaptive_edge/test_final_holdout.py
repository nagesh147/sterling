import pytest

from app.engines.adaptive_edge.final_holdout import (
    FinalHoldoutError,
    FinalHoldoutEvidence,
    HoldoutCandidate,
)


def candidate(**overrides):
    values = dict(
        candidate_id="candidate-1",
        evaluation_id="eval-1",
        result_fingerprint="result-1",
        test_observed=False,
        selection_influenced=False,
    )
    values.update(overrides)
    return HoldoutCandidate(**values)


def test_final_holdout_accepts_unobserved_unselected_candidate():
    evidence = FinalHoldoutEvidence.assemble(
        "holdout-1", "eval-1", candidate(), "dataset-1", "claim-1"
    )
    assert evidence.candidate.candidate_id == "candidate-1"


def test_final_holdout_rejects_test_observed_candidate():
    with pytest.raises(FinalHoldoutError):
        candidate(test_observed=True)


def test_final_holdout_rejects_selection_influenced_candidate():
    with pytest.raises(FinalHoldoutError):
        candidate(selection_influenced=True)


def test_final_holdout_rejects_mismatched_evaluation_identity():
    with pytest.raises(FinalHoldoutError):
        FinalHoldoutEvidence.assemble(
            "holdout-1", "eval-2", candidate(), "dataset-1", "claim-1"
        )
