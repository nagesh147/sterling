"""Selection-gate primitives for Adaptive Edge empirical similarity.

Canonical source: Master Mathematical Specification, §23.

The source requires a minimum effective sample size but does not prescribe
its estimator, threshold, neighbourhood size, or candidate-selection policy.
Accordingly this module provides only parameterized gate mechanics. The
weighted-sample ESS identity is exposed as a generic statistical utility and
is NOT presented as a recovered Adaptive Edge strategy definition.
"""
from __future__ import annotations

from math import isfinite
from typing import Sequence


class SimilaritySelectionError(ValueError):
    """Raised when similarity-selection inputs are invalid."""


def effective_sample_size(weights: Sequence[float]) -> float:
    """Generic weighted-sample ESS: (sum w)^2 / sum(w^2).

    This is a statistical utility, not a source-recovered Adaptive Edge
    parameter or selection policy.
    """
    if not weights:
        raise SimilaritySelectionError("weights must not be empty")
    if not all(isfinite(weight) and weight >= 0 for weight in weights):
        raise SimilaritySelectionError("weights must be finite and non-negative")
    total = sum(weights)
    squared_total = sum(weight * weight for weight in weights)
    if squared_total <= 0:
        raise SimilaritySelectionError("weights must contain positive mass")
    return (total * total) / squared_total


def passes_effective_sample_gate(
    effective_samples: float,
    minimum_effective_samples: float,
) -> bool:
    """Apply an explicitly supplied effective-sample sufficiency threshold."""
    if not isfinite(effective_samples) or effective_samples < 0:
        raise SimilaritySelectionError("effective_samples must be finite and non-negative")
    if not isfinite(minimum_effective_samples) or minimum_effective_samples <= 0:
        raise SimilaritySelectionError(
            "minimum_effective_samples must be finite and positive"
        )
    return effective_samples >= minimum_effective_samples
