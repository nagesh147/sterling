"""Research-only canonical A->K runner starting at the TrueData boundary.

The runner composes the existing causal market-event adapter with F-101..F-106.
It intentionally stops before F-107 because risk authorization requires a
separately governed account context. No production formula is unlocked here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.services.providers.truedata.adapter import TrueDataMarketDataAdapter
from .f101_f106_pipeline import F101F106PipelineInput, F101F106PipelineResult, evaluate_upstream


@dataclass(frozen=True)
class CanonicalAToF106Result:
    market_event: Any
    upstream: F101F106PipelineResult

    @property
    def downstream_admissible(self) -> bool:
        return self.upstream.eligible_for_downstream_execution


def run_truedata_bar_to_f106(
    symbol: str,
    bar_record: Mapping[str, Any],
    *,
    receipt_time_iso: str | None,
    feature_values: dict[str, float],
    quality_ok: bool,
    decision_time: str,
    probabilities: tuple[float, float, float],
    directional_edge: float,
    eligibility_reason: str,
    expected_gross_value: float | None,
    execution_cost: float,
    conservative_net_value: float | None,
    minimum_net_value: float,
    horizons: dict[str, float],
    selected_horizon: str,
    option_candidates: tuple,
    sequence: int | None = None,
) -> CanonicalAToF106Result:
    event = TrueDataMarketDataAdapter.create_bar_event(
        symbol, bar_record, receipt_time_iso=receipt_time_iso, sequence=sequence
    )
    upstream = evaluate_upstream(F101F106PipelineInput(
        feature_values=feature_values,
        quality_ok=quality_ok,
        observation_cutoff=event.available_at,
        decision_time=decision_time,
        probabilities=probabilities,
        directional_edge=directional_edge,
        eligibility_reason=eligibility_reason,
        expected_gross_value=expected_gross_value,
        execution_cost=execution_cost,
        conservative_net_value=conservative_net_value,
        minimum_net_value=minimum_net_value,
        horizons=horizons,
        selected_horizon=selected_horizon,
        option_candidates=option_candidates,
    ))
    return CanonicalAToF106Result(event, upstream)
