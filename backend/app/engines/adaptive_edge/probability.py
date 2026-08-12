"""Source-defined baseline probability estimation.

Implements only relationships supported by the canonical probability and
statistical-estimation specifications. Research parameters remain explicit
inputs and are never assigned strategy values here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


class ProbabilityError(ValueError):
    pass


class Outcome(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class HistoricalOutcome:
    outcome: Outcome
    weight: float = 1.0

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise ProbabilityError("observation weight must be positive")


@dataclass(frozen=True)
class ProbabilityState:
    p_up: float
    p_down: float
    p_neutral: float
    sample_size: int
    effective_sample_size: float
    status: str

    def __post_init__(self) -> None:
        probabilities = (self.p_up, self.p_down, self.p_neutral)
        if any(p < 0 or p > 1 for p in probabilities):
            raise ProbabilityError("probabilities must be in [0, 1]")
        probability_sum = sum(probabilities)
        if self.status == "INSUFFICIENT_DATA":
            if probability_sum > 1e-12:
                raise ProbabilityError(
                    "insufficient-data probabilities must be zero"
                )
        elif abs(probability_sum - 1.0) > 1e-12:
            raise ProbabilityError("probabilities must sum to one")
        if self.sample_size < 0 or self.effective_sample_size < 0:
            raise ProbabilityError("sample sizes cannot be negative")


from .statistics import (
    StatisticalError,
    effective_sample_size as _effective_sample_size,
)

def effective_sample_size(weights: Sequence[float]) -> float:
    """Domain-compatible ESS wrapper preserving ProbabilityError semantics."""
    if any(weight <= 0 for weight in weights):
        raise ProbabilityError("weights must be positive")
    try:
        return _effective_sample_size(weights)
    except StatisticalError as exc:
        raise ProbabilityError(str(exc)) from exc

def empirical_probability(
    observations: Iterable[HistoricalOutcome],
    *,
    minimum_effective_sample_size: float,
) -> ProbabilityState:
    """Estimate P(UP/DOWN/NEUTRAL) from an eligible historical population.

    The minimum evidence requirement is deliberately supplied by the caller;
    the source leaves its numerical threshold unfrozen.
    """
    rows = tuple(observations)
    if minimum_effective_sample_size < 0:
        raise ProbabilityError("minimum effective sample size cannot be negative")
    weights = tuple(row.weight for row in rows)
    ess = effective_sample_size(weights)
    if not rows or ess < minimum_effective_sample_size:
        return ProbabilityState(0.0, 0.0, 0.0, len(rows), ess, "INSUFFICIENT_DATA")
    total = sum(weights)
    counts = {outcome: sum(row.weight for row in rows if row.outcome is outcome) for outcome in Outcome}
    return ProbabilityState(
        counts[Outcome.UP] / total,
        counts[Outcome.DOWN] / total,
        counts[Outcome.NEUTRAL] / total,
        len(rows),
        ess,
        "OK",
    )


def beta_binomial_posterior_mean(
    successes: float,
    failures: float,
    *,
    alpha: float,
    beta: float,
) -> float:
    """Candidate binary Bayesian smoother; alpha/beta remain explicit research inputs."""
    if min(successes, failures, alpha, beta) < 0 or alpha + beta <= 0:
        raise ProbabilityError("invalid beta-binomial inputs")
    return (alpha + successes) / (alpha + beta + successes + failures)
