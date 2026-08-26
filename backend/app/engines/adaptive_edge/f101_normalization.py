"""Research-only F-101 empirical normalization boundary.

F-101 in the recovered Version 1.0 strategy is a causal, conditional
statistical normalization of feature values. This module deliberately does
not create a scalar "edge score" or freeze production parameters.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from types import MappingProxyType
from typing import Mapping, Sequence


@dataclass(frozen=True)
class F101Observation:
    """One historical feature observation available at a decision time."""

    timestamp: str
    value: float
    context: str = "GLOBAL"


@dataclass(frozen=True)
class F101NormalizationModel:
    """Frozen empirical CDFs fitted strictly from a training interval."""

    formula_id: str
    formula_version: str
    training_end: str
    distributions: Mapping[str, tuple[float, ...]]

    def __post_init__(self) -> None:
        if self.formula_id != "F-101":
            raise ValueError("F-101 normalization model requires formula_id F-101")
        _parse_timestamp(self.training_end, "training_end")
        frozen = {}
        for context, values in self.distributions.items():
            if not context:
                raise ValueError("normalization context is required")
            if not values:
                raise ValueError(f"normalization distribution is empty: {context}")
            if any(not isfinite(value) for value in values):
                raise ValueError(f"normalization distribution contains non-finite values: {context}")
            if tuple(sorted(values)) != tuple(values):
                raise ValueError(f"normalization distribution must be sorted: {context}")
            frozen[context] = tuple(values)
        object.__setattr__(self, "distributions", MappingProxyType(frozen))

    def transform(self, observation: F101Observation) -> float:
        """Return empirical CDF percentile using the frozen training distribution."""
        decision_time = _parse_timestamp(observation.timestamp, "timestamp")
        training_end = _parse_timestamp(self.training_end, "training_end")
        if decision_time < training_end:
            raise ValueError("decision timestamp precedes normalization training boundary")
        if not isfinite(observation.value):
            raise ValueError("feature value must be finite")
        values = self.distributions.get(observation.context)
        if values is None:
            raise ValueError(f"no normalization distribution for context: {observation.context}")

        # Empirical CDF: F(x) = count(v <= x) / n.
        import bisect

        return bisect.bisect_right(values, observation.value) / len(values)


def fit_f101(
    observations: Sequence[F101Observation],
    *,
    training_end: str,
    formula_version: str = "1.0-research",
) -> F101NormalizationModel:
    """Fit F-101 using observations available no later than ``training_end``.

    This is a research estimator. It intentionally exposes no production
    threshold, weighting scheme, or scalar feature score.
    """
    cutoff = _parse_timestamp(training_end, "training_end")
    grouped: dict[str, list[float]] = {}

    for observation in observations:
        timestamp = _parse_timestamp(observation.timestamp, "timestamp")
        if timestamp > cutoff:
            raise ValueError("training observation occurs after training_end")
        if not isfinite(observation.value):
            raise ValueError("training observation value must be finite")
        if not observation.context:
            raise ValueError("normalization context is required")
        grouped.setdefault(observation.context, []).append(observation.value)

    if not grouped:
        raise ValueError("F-101 requires at least one training observation")

    distributions = {context: tuple(sorted(values)) for context, values in grouped.items()}
    return F101NormalizationModel(
        formula_id="F-101",
        formula_version=formula_version,
        training_end=training_end,
        distributions=distributions,
    )


def _parse_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return parsed
