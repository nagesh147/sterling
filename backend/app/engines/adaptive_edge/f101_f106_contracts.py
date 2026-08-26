"""Fail-closed research contracts for Adaptive Edge F-101..F-106.

These contracts make the recovered strategy semantics executable for research
without promoting any empirical parameter or changing production registry
status. Every contract requires causal, explicit inputs and rejects missing
or non-finite values rather than silently substituting defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


class ResearchContractError(ValueError):
    pass


def _finite(name: str, value: float) -> float:
    if not isfinite(value):
        raise ResearchContractError(f"{name} must be finite")
    return value


@dataclass(frozen=True)
class F101NormalizedState:
    values: Mapping[str, float]
    quality_ok: bool
    observation_cutoff: str
    decision_time: str

    def __post_init__(self) -> None:
        if self.observation_cutoff > self.decision_time:
            raise ResearchContractError("F-101 lookahead: observation cutoff exceeds decision time")
        if not self.values:
            raise ResearchContractError("F-101 requires non-empty feature state")
        for name, value in self.values.items():
            _finite(name, value)
        if not self.quality_ok:
            raise ResearchContractError("F-101 feature quality is not sufficient")


@dataclass(frozen=True)
class F102ProbabilityState:
    bullish: float
    bearish: float
    neutral: float

    def __post_init__(self) -> None:
        probabilities = tuple(_finite(name, value) for name, value in (
            ("bullish", self.bullish), ("bearish", self.bearish), ("neutral", self.neutral)))
        if any(p < 0 or p > 1 for p in probabilities):
            raise ResearchContractError("F-102 probabilities must be in [0, 1]")
        if abs(sum(probabilities) - 1.0) > 1e-9:
            raise ResearchContractError("F-102 probabilities must sum to 1")


@dataclass(frozen=True)
class F103Eligibility:
    eligible: bool
    reason: str
    directional_edge: float
    data_quality_ok: bool

    def __post_init__(self) -> None:
        _finite("directional_edge", self.directional_edge)
        if not self.reason:
            raise ResearchContractError("F-103 requires an explicit eligibility reason")
        if self.eligible and not self.data_quality_ok:
            raise ResearchContractError("F-103 cannot admit low-quality data")


@dataclass(frozen=True)
class F104HorizonState:
    probabilities: Mapping[str, float]
    selected_horizon: str

    def __post_init__(self) -> None:
        if not self.probabilities or not self.selected_horizon:
            raise ResearchContractError("F-104 requires horizon distribution and selection")
        total = 0.0
        for name, value in self.probabilities.items():
            value = _finite(name, value)
            if value < 0 or value > 1:
                raise ResearchContractError("F-104 horizon probabilities must be in [0, 1]")
            total += value
        if abs(total - 1.0) > 1e-9:
            raise ResearchContractError("F-104 horizon probabilities must sum to 1")
        if self.selected_horizon not in self.probabilities:
            raise ResearchContractError("F-104 selected horizon absent from distribution")


@dataclass(frozen=True)
class F105Economics:
    expected_gross_value: float | None
    expected_execution_cost: float
    conservative_net_value: float | None
    minimum_net_value: float

    @property
    def eligible(self) -> bool:
        return self.conservative_net_value is not None and self.conservative_net_value >= self.minimum_net_value

    def __post_init__(self) -> None:
        if self.expected_gross_value is None:
            return
        _finite("expected_gross_value", self.expected_gross_value)
        _finite("expected_execution_cost", self.expected_execution_cost)
        _finite("minimum_net_value", self.minimum_net_value)
        if self.conservative_net_value is None:
            raise ResearchContractError("F-105 requires conservative net value when gross value exists")
        _finite("conservative_net_value", self.conservative_net_value)


@dataclass(frozen=True)
class F106OptionCandidate:
    instrument_id: str
    expected_net_value: float
    liquidity_ok: bool
    slippage_ok: bool
    risk_ok: bool
    data_quality_ok: bool

    @property
    def eligible(self) -> bool:
        return all((self.liquidity_ok, self.slippage_ok, self.risk_ok, self.data_quality_ok))

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ResearchContractError("F-106 requires instrument identity")
        _finite("expected_net_value", self.expected_net_value)


def select_f106_candidate(candidates: tuple[F106OptionCandidate, ...]) -> F106OptionCandidate | None:
    eligible = [candidate for candidate in candidates if candidate.eligible]
    if not eligible:
        return None
    return max(eligible, key=lambda candidate: (candidate.expected_net_value, candidate.instrument_id))
