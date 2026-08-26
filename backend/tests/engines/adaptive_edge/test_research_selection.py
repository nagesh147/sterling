from __future__ import annotations

import pytest

from app.engines.adaptive_edge.research_selection import (
    CandidateEvaluation,
    ResearchSelectionError,
    ResearchSelectionRegistry,
    SelectionDecision,
)


def candidate(candidate_id: str, *, test_observed: bool = False, selection_influenced: bool = False) -> CandidateEvaluation:
    return CandidateEvaluation(
        candidate_id=candidate_id,
        evaluation_id="eval-1",
        code_version="code-1",
        feature_version="feature-1",
        label_version="label-1",
        execution_version="execution-1",
        parameter_fingerprint=f"params-{candidate_id}",
        result_fingerprint=f"result-{candidate_id}",
        test_observed=test_observed,
        selection_influenced=selection_influenced,
    )


def test_preserves_entire_candidate_population_and_is_deterministic() -> None:
    first = ResearchSelectionRegistry.build([candidate("b"), candidate("a")])
    second = ResearchSelectionRegistry.build([candidate("a"), candidate("b")])

    assert first.selection_population_size == 2
    assert first.registry_fingerprint == second.registry_fingerprint
    assert first.final_test_eligible()


def test_rejects_duplicate_candidate() -> None:
    with pytest.raises(ResearchSelectionError, match="duplicate candidate_id"):
        ResearchSelectionRegistry.build([candidate("a"), candidate("a")])


def test_selected_candidate_must_belong_to_research_population() -> None:
    decision = SelectionDecision("missing", "policy-1", "rationale", "v1")
    with pytest.raises(ResearchSelectionError, match="selected candidate"):
        ResearchSelectionRegistry.build([candidate("a")], decision)


def test_test_observation_that_influences_selection_contaminates_final_test() -> None:
    registry = ResearchSelectionRegistry.build([
        candidate("a", test_observed=True, selection_influenced=True),
        candidate("b", test_observed=True),
    ])

    assert registry.test_observed_candidate_ids == ("a", "b")
    assert registry.test_contaminated_candidate_ids == ("a",)
    assert not registry.final_test_eligible()


def test_selection_influence_requires_test_observation() -> None:
    with pytest.raises(ResearchSelectionError, match="test observation"):
        candidate("a", selection_influenced=True)
