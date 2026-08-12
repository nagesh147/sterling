import pytest

from app.engines.adaptive_edge.similarity_v21 import SimilarityConfig, SimilarityError, SimilarityObservation, empirical_similarity, similarity_weight


def test_similarity_weight_decreases_with_distance():
    assert similarity_weight(0.0, 1.0) == pytest.approx(1.0)
    assert similarity_weight(1.0, 1.0) < similarity_weight(0.0, 1.0)


def test_similarity_selects_nearest_observations_and_normalizes_probabilities():
    result = empirical_similarity(
        (
            SimilarityObservation(0.1, "UP"),
            SimilarityObservation(0.2, "UP"),
            SimilarityObservation(0.3, "DOWN"),
        ),
        config=SimilarityConfig(tau=1.0, maximum_neighbors=3, minimum_effective_sample_size=1),
    )
    assert sum(result.probabilities.values()) == pytest.approx(1.0)
    assert result.probabilities["UP"] > result.probabilities["DOWN"]
    assert result.sample_size == 3


def test_similarity_fails_closed_when_evidence_is_insufficient():
    with pytest.raises(SimilarityError, match="insufficient effective"):
        empirical_similarity(
            (SimilarityObservation(100.0, "UP"),),
            config=SimilarityConfig(tau=1.0, maximum_neighbors=1, minimum_effective_sample_size=2),
        )
