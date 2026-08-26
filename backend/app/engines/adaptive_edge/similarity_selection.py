"""Selection-gate primitives for Adaptive Edge empirical similarity.

Canonical source: Master Mathematical Specification, §23.

The source requires a minimum effective sample size but does not prescribe
its estimator, threshold, neighbourhood size, or candidate-selection policy.
Accordingly this module exposes only explicit, parameterized mechanics. It
never supplies strategy defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, Sequence


class SimilaritySelectionError(ValueError):
    """Raised when similarity-selection inputs are invalid."""


SelectionState = Literal["INSUFFICIENT_EVIDENCE", "SELECTED"]


@dataclass(frozen=True)
class SimilarityCandidate:
    candidate_id: str
    distance: float
    weight: float


@dataclass(frozen=True)
class SimilaritySelectionPolicy:
    """Explicit selection constraints; no strategy defaults are supplied."""

    minimum_effective_sample_size: float
    neighbourhood_size: int | None = None
    maximum_distance: float | None = None


@dataclass(frozen=True)
class SimilaritySelectionResult:
    state: SelectionState
    candidates: tuple[SimilarityCandidate, ...]
    effective_sample_size: float
    reason: str | None = None


from .statistics import (
    StatisticalError,
    effective_sample_size as _effective_sample_size,
)

def effective_sample_size(weights: Sequence[float]) -> float:
    """Domain-compatible ESS wrapper preserving selection error semantics."""
    try:
        return _effective_sample_size(weights)
    except StatisticalError as exc:
        raise SimilaritySelectionError(str(exc)) from exc

def passes_effective_sample_gate(
    effective_samples: float,
    minimum_effective_samples: float,
) -> bool:
    """Apply an explicitly supplied effective-sample sufficiency threshold."""
    if not isfinite(effective_samples) or effective_samples < 0:
        raise SimilaritySelectionError("effective_samples must be finite and non-negative")
    if not isfinite(minimum_effective_samples) or minimum_effective_samples <= 0:
        raise SimilaritySelectionError("minimum_effective_samples must be finite and positive")
    return effective_samples >= minimum_effective_samples


def select_candidates(
    candidates: Sequence[SimilarityCandidate],
    policy: SimilaritySelectionPolicy,
) -> SimilaritySelectionResult:
    """Apply only explicitly supplied candidate-selection constraints.

    Ordering is deterministic by (distance, candidate_id). This function does
    not imply that these constraints are the canonical Adaptive Edge policy.
    """
    if not isfinite(policy.minimum_effective_sample_size) or policy.minimum_effective_sample_size <= 0:
        raise SimilaritySelectionError("minimum_effective_sample_size must be finite and positive")
    if policy.neighbourhood_size is not None and policy.neighbourhood_size <= 0:
        raise SimilaritySelectionError("neighbourhood_size must be positive when supplied")
    if policy.maximum_distance is not None and (
        not isfinite(policy.maximum_distance) or policy.maximum_distance < 0
    ):
        raise SimilaritySelectionError("maximum_distance must be finite and non-negative when supplied")

    eligible = []
    for candidate in candidates:
        if not candidate.candidate_id:
            raise SimilaritySelectionError("candidate_id must not be empty")
        if not isfinite(candidate.distance) or candidate.distance < 0:
            raise SimilaritySelectionError("candidate distance must be finite and non-negative")
        if not isfinite(candidate.weight) or candidate.weight < 0:
            raise SimilaritySelectionError("candidate weight must be finite and non-negative")
        if policy.maximum_distance is None or candidate.distance <= policy.maximum_distance:
            eligible.append(candidate)

    eligible.sort(key=lambda candidate: (candidate.distance, candidate.candidate_id))
    if policy.neighbourhood_size is not None:
        eligible = eligible[: policy.neighbourhood_size]

    if not eligible:
        return SimilaritySelectionResult("INSUFFICIENT_EVIDENCE", (), 0.0, "no eligible candidates")

    ess = effective_sample_size([candidate.weight for candidate in eligible])
    if not passes_effective_sample_gate(ess, policy.minimum_effective_sample_size):
        return SimilaritySelectionResult(
            "INSUFFICIENT_EVIDENCE",
            tuple(eligible),
            ess,
            "minimum effective sample size not met",
        )
    return SimilaritySelectionResult("SELECTED", tuple(eligible), ess)
