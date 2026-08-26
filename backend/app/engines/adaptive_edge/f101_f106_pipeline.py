"""Pipeline adapter that makes F-101..F-106 contracts causal and composable.

This is intentionally a research-stage adapter. It does not alter formula
registry status or authorize execution. Its only job is to enforce the
upstream invariants before downstream A->K stages are allowed to consume them.
"""
from __future__ import annotations

from dataclasses import dataclass

from .f101_f106_contracts import (
    F101NormalizedState,
    F102ProbabilityState,
    F103Eligibility,
    F104HorizonState,
    F105Economics,
    F106OptionCandidate,
    select_f106_candidate,
)


@dataclass(frozen=True)
class F101F106PipelineInput:
    feature_values: dict[str, float]
    quality_ok: bool
    observation_cutoff: str
    decision_time: str
    probabilities: tuple[float, float, float]
    directional_edge: float
    eligibility_reason: str
    expected_gross_value: float | None
    execution_cost: float
    conservative_net_value: float | None
    minimum_net_value: float
    horizons: dict[str, float]
    selected_horizon: str
    option_candidates: tuple[F106OptionCandidate, ...]


@dataclass(frozen=True)
class F101F106PipelineResult:
    normalized: F101NormalizedState
    prediction: F102ProbabilityState
    eligibility: F103Eligibility
    horizon: F104HorizonState
    economics: F105Economics
    selected_option: F106OptionCandidate | None

    @property
    def eligible_for_downstream_execution(self) -> bool:
        return (
            self.eligibility.eligible
            and self.economics.eligible
            and self.selected_option is not None
        )


def evaluate_upstream(input_data: F101F106PipelineInput) -> F101F106PipelineResult:
    normalized = F101NormalizedState(
        input_data.feature_values,
        input_data.quality_ok,
        input_data.observation_cutoff,
        input_data.decision_time,
    )
    prediction = F102ProbabilityState(*input_data.probabilities)
    eligibility = F103Eligibility(
        input_data.directional_edge > 0,
        input_data.eligibility_reason,
        input_data.directional_edge,
        input_data.quality_ok,
    )
    horizon = F104HorizonState(input_data.horizons, input_data.selected_horizon)
    economics = F105Economics(
        input_data.expected_gross_value,
        input_data.execution_cost,
        input_data.conservative_net_value,
        input_data.minimum_net_value,
    )
    selected_option = select_f106_candidate(input_data.option_candidates)
    return F101F106PipelineResult(
        normalized, prediction, eligibility, horizon, economics, selected_option
    )
