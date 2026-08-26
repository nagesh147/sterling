"""V2.1 empirical horizon-outcome distribution.

The proposed definition uses a configured bar horizon and an empirical
conditional distribution of future underlying returns. The caller must supply
causally valid observations; this module rejects observations that are not
strictly after the decision timestamp.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from statistics import mean
from typing import Sequence


class HorizonError(ValueError):
    pass


@dataclass(frozen=True)
class HorizonObservation:
    decision_time: datetime
    observation_time: datetime
    future_return: float


@dataclass(frozen=True)
class HorizonDistribution:
    horizon_bars: int
    sample_size: int
    mean_return: float
    standard_deviation: float
    sorted_returns: tuple[float, ...]

    def quantile(self, probability: float) -> float:
        if not 0 <= probability <= 1:
            raise HorizonError("probability must be in [0, 1]")
        if not self.sorted_returns:
            raise HorizonError("distribution has no observations")
        if len(self.sorted_returns) == 1:
            return self.sorted_returns[0]
        position = probability * (len(self.sorted_returns) - 1)
        lower = int(position)
        upper = min(lower + 1, len(self.sorted_returns) - 1)
        fraction = position - lower
        return self.sorted_returns[lower] + fraction * (self.sorted_returns[upper] - self.sorted_returns[lower])


def build_horizon_distribution(
    observations: Sequence[HorizonObservation],
    *,
    horizon_bars: int,
) -> HorizonDistribution:
    if horizon_bars <= 0:
        raise HorizonError("horizon_bars must be positive")
    if not observations:
        raise HorizonError("horizon distribution requires observations")
    for observation in observations:
        if observation.observation_time <= observation.decision_time:
            raise HorizonError("future outcome observation must be after decision time")
    returns = tuple(sorted(observation.future_return for observation in observations))
    average = mean(returns)
    variance = mean((value - average) ** 2 for value in returns)
    return HorizonDistribution(horizon_bars, len(returns), average, sqrt(variance), returns)
