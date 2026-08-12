import pytest

from app.engines.adaptive_edge.similarity_selection import (
    SimilarityCandidate,
    SimilaritySelectionError,
    SimilaritySelectionPolicy,
    effective_sample_size,
    passes_effective_sample_gate,
    select_candidates,
)


def test_effective_sample_size_for_equal_weights_equals_count():
    assert effective_sample_size((1.0, 1.0, 1.0, 1.0)) == 4.0


def test_effective_sample_size_reflects_concentration():
    assert effective_sample_size((4.0, 0.0, 0.0, 0.0)) == 1.0


def test_effective_sample_size_rejects_invalid_weights():
    with pytest.raises(SimilaritySelectionError, match="finite and non-negative"):
        effective_sample_size((1.0, -1.0))


def test_effective_sample_size_rejects_zero_mass():
    with pytest.raises(SimilaritySelectionError, match="positive mass"):
        effective_sample_size((0.0, 0.0))


def test_gate_requires_explicit_threshold():
    assert passes_effective_sample_gate(30.0, 30.0)
    assert not passes_effective_sample_gate(29.999, 30.0)


def test_gate_rejects_non_positive_threshold():
    with pytest.raises(SimilaritySelectionError, match="positive"):
        passes_effective_sample_gate(1.0, 0.0)


def test_selection_is_deterministic_by_distance_then_id():
    result = select_candidates(
        (
            SimilarityCandidate("b", 1.0, 1.0),
            SimilarityCandidate("a", 1.0, 1.0),
        ),
        SimilaritySelectionPolicy(minimum_effective_sample_size=1.0),
    )
    assert result.state == "SELECTED"
    assert tuple(c.candidate_id for c in result.candidates) == ("a", "b")


def test_selection_can_apply_explicit_neighbourhood_size():
    result = select_candidates(
        (
            SimilarityCandidate("a", 1.0, 1.0),
            SimilarityCandidate("b", 2.0, 1.0),
        ),
        SimilaritySelectionPolicy(minimum_effective_sample_size=1.0, neighbourhood_size=1),
    )
    assert result.state == "SELECTED"
    assert tuple(c.candidate_id for c in result.candidates) == ("a",)


def test_selection_reports_insufficient_evidence_without_fallback():
    result = select_candidates(
        (SimilarityCandidate("a", 1.0, 1.0),),
        SimilaritySelectionPolicy(minimum_effective_sample_size=2.0),
    )
    assert result.state == "INSUFFICIENT_EVIDENCE"
    assert result.reason == "minimum effective sample size not met"


def test_selection_can_apply_explicit_distance_cutoff():
    result = select_candidates(
        (
            SimilarityCandidate("a", 1.0, 1.0),
            SimilarityCandidate("b", 3.0, 1.0),
        ),
        SimilaritySelectionPolicy(minimum_effective_sample_size=1.0, maximum_distance=2.0),
    )
    assert tuple(c.candidate_id for c in result.candidates) == ("a",)
