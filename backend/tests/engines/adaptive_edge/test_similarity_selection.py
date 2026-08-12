import pytest

from app.engines.adaptive_edge.similarity_selection import (
    SimilaritySelectionError,
    effective_sample_size,
    passes_effective_sample_gate,
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
