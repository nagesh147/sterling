"""Provider-neutral statistical utilities used by Adaptive Edge components.

These are generic statistical mechanics, not recovered strategy parameters.
"""
from __future__ import annotations

from math import isfinite
from typing import Sequence


class StatisticalError(ValueError):
    """Raised when statistical inputs are invalid."""


def effective_sample_size(weights: Sequence[float]) -> float:
    """Compute weighted effective sample size.

    ESS = (sum(w))^2 / sum(w^2)

    The caller remains responsible for deciding whether the resulting ESS
    satisfies a strategy-specific evidence threshold.
    """
    if not weights:
        return 0.0
    if not all(isfinite(weight) and weight >= 0 for weight in weights):
        raise StatisticalError("weights must be finite and non-negative")
    total = sum(weights)
    squared_total = sum(weight * weight for weight in weights)
    if squared_total <= 0:
        raise StatisticalError("weights must contain positive mass")
    return (total * total) / squared_total
