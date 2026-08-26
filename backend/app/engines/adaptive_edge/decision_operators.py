"""Source-defined decision operators for Adaptive Edge.

These operators close the mathematical gaps between already-implemented
probability/economic inputs and the decision boundary. They accept learned or
validated quantities as inputs and never invent strategy thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence


class DecisionOperatorError(ValueError):
    """Raised when a decision operator receives invalid inputs."""


@dataclass(frozen=True)
class TargetStopEstimate:
    candidate_id: str
    p_target: float
    expected_gain: float
    p_stop: float
    expected_loss: float
    costs: float

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise DecisionOperatorError("candidate_id must not be empty")
        values = (self.p_target, self.expected_gain, self.p_stop, self.expected_loss, self.costs)
        if not all(isfinite(value) for value in values):
            raise DecisionOperatorError("target/stop inputs must be finite")
        if not 0.0 <= self.p_target <= 1.0 or not 0.0 <= self.p_stop <= 1.0:
            raise DecisionOperatorError("target/stop probabilities must be in [0, 1]")
        if self.expected_gain < 0 or self.expected_loss < 0 or self.costs < 0:
            raise DecisionOperatorError("gain, loss, and costs must be non-negative")

    @property
    def expected_value(self) -> float:
        return (
            self.p_target * self.expected_gain
            - self.p_stop * self.expected_loss
            - self.costs
        )


@dataclass(frozen=True)
class SelectedDecision:
    candidate_id: str
    conservative_ev: float


def select_max_conservative_ev(
    candidates: Sequence[tuple[str, float]],
) -> SelectedDecision:
    """Implement §33: argmax ConservativeEV over supplied candidates."""
    if not candidates:
        raise DecisionOperatorError("at least one candidate is required")
    validated: list[tuple[str, float]] = []
    for candidate_id, value in candidates:
        if not candidate_id.strip():
            raise DecisionOperatorError("candidate_id must not be empty")
        if not isfinite(value):
            raise DecisionOperatorError("conservative EV must be finite")
        validated.append((candidate_id, value))
    candidate_id, value = max(validated, key=lambda item: item[1])
    return SelectedDecision(candidate_id, value)


def target_stop_expected_value(estimate: TargetStopEstimate) -> float:
    """Implement §33 EV(s,m) for supplied target/stop estimates."""
    return estimate.expected_value


def select_target_stop(
    candidates: Sequence[TargetStopEstimate],
    conservative_values: Sequence[float],
) -> SelectedDecision:
    """Select the target/stop pair with maximum supplied ConservativeEV."""
    if not candidates:
        raise DecisionOperatorError("at least one target/stop candidate is required")
    if len(candidates) != len(conservative_values):
        raise DecisionOperatorError("candidate and conservative-value dimensions differ")
    return select_max_conservative_ev(
        tuple((candidate.candidate_id, value) for candidate, value in zip(candidates, conservative_values))
    )


def entry_gate(
    *,
    data_ok: bool,
    directional_edge_ok: bool,
    expected_ev: float,
    conservative_ev: float,
    liquidity_ok: bool,
    slippage_ok: bool,
    risk_ok: bool,
) -> bool:
    """Implement the §35 Boolean entry predicate for a supplied instrument."""
    return (
        data_ok
        and directional_edge_ok
        and expected_ev > 0.0
        and conservative_ev > 0.0
        and liquidity_ok
        and slippage_ok
        and risk_ok
    )


def no_trade_from_conservative_ev(conservative_ev: float) -> bool:
    """Implement §34: non-positive conservative EV is not actionable."""
    if not isfinite(conservative_ev):
        raise DecisionOperatorError("conservative EV must be finite")
    return conservative_ev <= 0.0
