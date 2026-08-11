"""Causal contextual normalization for Adaptive Edge §19.

The normalizer is deliberately parameter-free: it computes an empirical CDF
from observations whose availability time is <= the decision time and whose
context matches the current context. No universal fixed threshold is created.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from bisect import bisect_right
from typing import Iterable


@dataclass(frozen=True)
class NormalizationContext:
    instrument: str
    time_of_day: str
    volatility_state: str | None = None
    expiry_state: str | None = None
    market_regime: str | None = None


@dataclass(frozen=True)
class Observation:
    value: float
    available_at: datetime
    context: NormalizationContext


@dataclass(frozen=True)
class NormalizedValue:
    value: float
    percentile: float
    sample_size: int


def conditional_percentile(
    value: float,
    *,
    decision_time: datetime,
    context: NormalizationContext,
    history: Iterable[Observation],
) -> NormalizedValue:
    """Compute F(x_t | Context_t, Data<=t) using an empirical CDF."""
    usable = sorted(
        obs.value
        for obs in history
        if obs.available_at <= decision_time and obs.context == context
    )
    if not usable:
        raise ValueError("insufficient causal normalization history")
    rank = bisect_right(usable, value)
    return NormalizedValue(
        value=value,
        percentile=rank / len(usable),
        sample_size=len(usable),
    )
