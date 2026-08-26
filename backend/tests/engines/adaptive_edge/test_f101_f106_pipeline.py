from __future__ import annotations

import pytest

from app.engines.adaptive_edge.f101_f106_contracts import F106OptionCandidate, ResearchContractError
from app.engines.adaptive_edge.f101_f106_pipeline import F101F106PipelineInput, evaluate_upstream


def make_input(**overrides):
    values = dict(
        feature_values={"vwap_distance": 0.4, "poc_distance": 0.2, "cvd_slope": 1.0},
        quality_ok=True,
        observation_cutoff="2026-08-19T09:30:00Z",
        decision_time="2026-08-19T09:30:00Z",
        probabilities=(0.6, 0.2, 0.2),
        directional_edge=0.25,
        eligibility_reason="directional_breakout",
        expected_gross_value=50.0,
        execution_cost=10.0,
        conservative_net_value=40.0,
        minimum_net_value=20.0,
        horizons={"MICRO": 0.2, "SCALP": 0.5, "INTRADAY": 0.3},
        selected_horizon="SCALP",
        option_candidates=(
            F106OptionCandidate("NIFTY-ATM-CE", 35.0, True, True, True, True),
            F106OptionCandidate("NIFTY-OTM-CE", 50.0, True, True, True, True),
        ),
    )
    values.update(overrides)
    return F101F106PipelineInput(**values)


def test_f101_f106_pipeline_produces_downstream_eligible_result():
    result = evaluate_upstream(make_input())
    assert result.eligible_for_downstream_execution is True
    assert result.selected_option.instrument_id == "NIFTY-OTM-CE"


def test_f101_failure_stops_pipeline_before_downstream_admission():
    with pytest.raises(ResearchContractError, match="lookahead"):
        evaluate_upstream(make_input(
            observation_cutoff="2026-08-19T09:31:00Z",
            decision_time="2026-08-19T09:30:00Z",
        ))


def test_f105_failure_produces_no_downstream_eligibility():
    result = evaluate_upstream(make_input(
        expected_gross_value=None,
        conservative_net_value=None,
    ))
    assert result.economics.eligible is False
    assert result.eligible_for_downstream_execution is False


def test_f106_failure_produces_no_downstream_eligibility():
    result = evaluate_upstream(make_input(
        option_candidates=(F106OptionCandidate("NIFTY-ATM-CE", 50.0, False, True, True, True),)
    ))
    assert result.selected_option is None
    assert result.eligible_for_downstream_execution is False
