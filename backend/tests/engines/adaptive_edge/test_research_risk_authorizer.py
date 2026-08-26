from __future__ import annotations

import pytest

from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
from app.engines.adaptive_edge.research_risk_authorizer import ResearchRiskAuthorizer
from app.engines.adaptive_edge.risk_sizing import (
    ExecutionCostParameters,
    ParameterEstimationMethod,
    ParameterMetadata,
    ParameterValidationStatus,
    SizingParameters,
)


def p(name: str, value: float) -> ParameterMetadata:
    return ParameterMetadata(
        name=name,
        value=value,
        units="INR/unit",
        version="test-1",
        provenance="research-test",
        estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
        validation_status=ParameterValidationStatus.VALIDATED,
    )


def costs() -> ExecutionCostParameters:
    return ExecutionCostParameters(
        p("spread", 1), p("slippage", .5), p("brokerage", .1),
        p("exchange", .05), p("taxes", .05), p("latency", .2),
    )


def sizing() -> SizingParameters:
    return SizingParameters(p("max_position", 100), p("capital", 100_000), p("lot", 25))


def authorization(state: RiskState = RiskState.AUTHORIZED) -> RiskAuthorization:
    return RiskAuthorization(
        opportunity_id="opp-1",
        authorized_risk=5_000,
        risk_state=state,
        policy_version="test-1",
        issued_at="2026-08-19T09:15:00+05:30",
    )


def test_research_risk_adapter_consumes_authorization_and_sizes_lots() -> None:
    result = ResearchRiskAuthorizer().assess(
        authorization(),
        entry_price=100,
        initial_stop=90,
        cost_parameters=costs(),
        sizing_parameters=sizing(),
    )
    assert result.risk_per_unit.effective_risk_per_unit == pytest.approx(11.9)
    assert result.sizing.final_quantity % 25 == 0
    assert result.sizing.effective_authorized_risk <= 5_000


def test_research_risk_adapter_cannot_bypass_unauthorized_state() -> None:
    with pytest.raises(ValueError, match="Risk authorization"):
        ResearchRiskAuthorizer().assess(
            authorization(RiskState.FROZEN),
            entry_price=100,
            initial_stop=90,
            cost_parameters=costs(),
            sizing_parameters=sizing(),
        )
