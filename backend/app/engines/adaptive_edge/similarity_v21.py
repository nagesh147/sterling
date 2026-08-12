"""Explicit V2.1 empirical-similarity estimator.

The estimator uses exponential distance weighting, deterministic nearest-neighbor
selection, and an explicit effective-sample-size gate. All research choices are
configuration rather than hidden constants.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Sequence

from .statistics import effective_sample_size


class SimilarityError(ValueError):
    pass


@dataclass(frozen=True)
class SimilarityObservation:
    distance: float
    outcome: str


@dataclass(frozen=True)
class SimilarityConfig:
    tau: float = 1.0
    maximum_neighbors: int = 100
    minimum_effective_sample_size: float = 5.0

    def __post_init__(self) -> None:
        if self.tau <= 0 or self.maximum_neighbors <= 0 or self.minimum_effective_sample_size < 0:
            raise SimilarityError("invalid similarity configuration")


@dataclass(frozen=True)
class SimilarityResult:
    probabilities: dict[str, float]
    sample_size: int
    effective_sample_size: float


def similarity_weight(distance: float, tau: float) -> float:
    if distance < 0 or tau <= 0:
        raise SimilarityError("distance must be non-negative and tau positive")
    return exp(-distance / tau)


def empirical_similarity(
    observations: Sequence[SimilarityObservation],
    *,
    config: SimilarityConfig,
) -> SimilarityResult:
    if not observations:
        raise SimilarityError("similarity requires observations")
    if any(observation.distance < 0 for observation in observations):
        raise SimilarityError("distances must be non-negative")
    selected = sorted(observations, key=lambda observation: (observation.distance, observation.outcome))[: config.maximum_neighbors]
    weights = [similarity_weight(observation.distance, config.tau) for observation in selected]
    ess = effective_sample_size(weights)
    if ess < config.minimum_effective_sample_size:
        raise SimilarityError("insufficient effective similarity evidence")
    total = sum(weights)
    probabilities: dict[str, float] = {}
    for observation, weight in zip(selected, weights):
        probabilities[observation.outcome] = probabilities.get(observation.outcome, 0.0) + weight / total
    return SimilarityResult(probabilities, len(selected), ess)
