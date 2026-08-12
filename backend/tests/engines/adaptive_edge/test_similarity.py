from math import isclose

import pytest

from app.engines.adaptive_edge.similarity import (
    SimilarityInputError,
    similarity_weight,
    weighted_distance,
    z_score,
)


def test_z_score_uses_source_definition():
    assert z_score(12.0, 10.0, 2.0) == 1.0


def test_weighted_distance_is_zero_for_identical_vectors():
    assert weighted_distance((1.0, 2.0), (1.0, 2.0), (1.0, 1.0)) == 0.0


def test_weighted_distance_matches_canonical_operator():
    distance = weighted_distance((1.0, 2.0), (3.0, 1.0), (2.0, 4.0))
    assert isclose(distance, 4.0**0.5 * 2.0, rel_tol=1e-12)


def test_similarity_weight_matches_canonical_operator():
    assert isclose(similarity_weight(2.0, 4.0), 1.0 / 2.718281828459045, rel_tol=1e-12)


def test_dimension_mismatch_is_rejected():
    with pytest.raises(SimilarityInputError, match="equal dimensions"):
        weighted_distance((1.0,), (1.0, 2.0), (1.0, 1.0))


def test_negative_feature_weight_is_rejected():
    with pytest.raises(SimilarityInputError, match="non-negative"):
        weighted_distance((1.0,), (2.0,), (-1.0,))


def test_zero_standard_deviation_is_rejected():
    with pytest.raises(SimilarityInputError, match="positive"):
        z_score(1.0, 1.0, 0.0)


def test_non_positive_tau_is_rejected():
    with pytest.raises(SimilarityInputError, match="positive"):
        similarity_weight(1.0, 0.0)
