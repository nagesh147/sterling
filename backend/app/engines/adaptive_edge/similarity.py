"""Source-defined empirical similarity operators for Adaptive Edge.

Canonical source: Master Mathematical Specification, §23.

This module implements only the exact operators recovered in the source. It
intentionally does not choose feature weights, neighbourhood size, effective
sample thresholds, or tau-learning policy.
"""
from __future__ import annotations

from math import exp, isfinite, sqrt
from typing import Sequence


class SimilarityInputError(ValueError):
    """Raised when a similarity operator receives invalid mathematical input."""


def _validate_vector(name: str, values: Sequence[float]) -> None:
    if not values:
        raise SimilarityInputError(f"{name} must not be empty")
    if not all(isfinite(value) for value in values):
        raise SimilarityInputError(f"{name} must contain only finite values")


def z_score(value: float, mean: float, stddev: float) -> float:
    """Compute Z_i = (X_i - mu_i) / sigma_i."""
    if not all(isfinite(v) for v in (value, mean, stddev)):
        raise SimilarityInputError("value, mean and stddev must be finite")
    if stddev <= 0:
        raise SimilarityInputError("stddev must be positive")
    return (value - mean) / stddev


def weighted_distance(
    target: Sequence[float],
    candidate: Sequence[float],
    weights: Sequence[float],
) -> float:
    """Compute d(X_t,X_j) = sqrt(sum(w_i * (Z_i,t - Z_i,j)^2))."""
    _validate_vector("target", target)
    _validate_vector("candidate", candidate)
    _validate_vector("weights", weights)
    if not (len(target) == len(candidate) == len(weights)):
        raise SimilarityInputError("target, candidate and weights must have equal dimensions")
    if any(weight < 0 for weight in weights):
        raise SimilarityInputError("weights must be non-negative")
    return sqrt(sum(weight * (x - y) ** 2 for x, y, weight in zip(target, candidate, weights)))


def similarity_weight(distance: float, tau: float) -> float:
    """Compute w_j = exp(-d_j^2 / tau)."""
    if not isfinite(distance) or distance < 0:
        raise SimilarityInputError("distance must be finite and non-negative")
    if not isfinite(tau) or tau <= 0:
        raise SimilarityInputError("tau must be finite and positive")
    return exp(-(distance**2) / tau)
