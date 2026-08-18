"""Research-only F-104 adaptive horizon distribution."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence


# Preserve the six buckets explicitly defined by the recovered V1 source.
HORIZON_BUCKETS = (
    "MICRO_SCALP",      # T < 3m
    "SHORT_SCALP",      # 3m <= T < 5m
    "SCALP",            # 5m <= T < 15m
    "EXTENDED_SCALP",   # 15m <= T < 30m
    "INTRADAY",         # 30m <= T < 45m
    "LONG_TAIL",        # T > 45m
)


@dataclass(frozen=True)
class HorizonDistribution:
    """Probability state for future trade duration.

    The >45m interval is retained as an open-ended tail; no arbitrary
    midpoint is introduced.
    """

    probabilities: tuple[float, ...]
    formula_id: str = "F-104"
    formula_version: str = "1.0-research"

    def __post_init__(self) -> None:
        if len(self.probabilities) != len(HORIZON_BUCKETS):
            raise ValueError("F-104 requires exactly six horizon probabilities")
        if any(not isfinite(p) for p in self.probabilities):
            raise ValueError("horizon probabilities must be finite")
        if any(p < 0.0 for p in self.probabilities):
            raise ValueError("horizon probabilities cannot be negative")
        if abs(sum(self.probabilities) - 1.0) > 1e-9:
            raise ValueError("horizon probabilities must sum to 1")

    @property
    def management_class(self) -> str:
        """Return the dominant management bucket as a derived state only."""
        return HORIZON_BUCKETS[max(range(len(self.probabilities)), key=self.probabilities.__getitem__)]

    @property
    def confidence(self) -> float:
        return max(self.probabilities)


def distribution_from_scores(scores: Sequence[float]) -> HorizonDistribution:
    """Convert research scores into a deterministic probability vector.

    Softmax is only a research boundary. Coefficients and model fitting remain
    unfrozen and require chronological walk-forward validation before any
    production promotion.
    """
    if len(scores) != len(HORIZON_BUCKETS):
        raise ValueError("F-104 requires six horizon scores")
    if any(not isfinite(score) for score in scores):
        raise ValueError("horizon scores must be finite")

    import math

    maximum = max(scores)
    exponentials = tuple(math.exp(score - maximum) for score in scores)
    total = sum(exponentials)
    if not isfinite(total) or total <= 0.0:
        raise ValueError("unable to normalize horizon scores")

    return HorizonDistribution(tuple(value / total for value in exponentials))
