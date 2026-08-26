from __future__ import annotations

from dataclasses import replace

import pytest

from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
from app.engines.adaptive_edge.risk_sizing import (
    ExecutionCostParameters,
    ParameterEstimationMethod,
    ParameterMetadata,
    ParameterValidationStatus,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
)


def p(name: str, value: float, units: str = "INR") -> ParameterMetadata:
    return ParameterMetadata(
        name=name,
        value=value,
        units=units,
        version="test-1",
        provenance="A214",
        estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
        validation_status=ParameterValidationStatus.VALIDATED,
    )


def costs() -> ExecutionCostParameters:
    return ExecutionCostParameters(
        p("spread", 1), p("slippage", 0.5), p("brokerage", 0.1),
        p("exchange", 0.05), p("taxes", 0.05), p("latency", 0.2),
    )


def sizing() -> SizingParameters:
    return SizingParameters(
        max_position_qty=p("max_position_qty", 100),
        max_capital_allocation=p("max_capital_allocation", 100_000),
        lot_size=p("lot_size", 25),
    )


def auth(amount: float = 5_000) -> RiskAuthorization:
    return RiskAuthorization("test-opportunity", amount, RiskState.AUTHORIZED, "test-policy", "2026-08-19T03:46:00+00:00")


def test_f108_returns_valid_lot_multiple() -> None:
    risk = calculate_risk_per_unit(100, 90, costs())
    result = calculate_position_sizing(auth(), risk, sizing())
    assert result.valid
    assert result.final_quantity % 25 == 0
    assert result.effective_authorized_risk <= 5_000


def test_f108_never_exceeds_max_position_quantity() -> None:
    risk = calculate_risk_per_unit(100, 99, costs())
    result = calculate_position_sizing(auth(100_000), risk, sizing())
    assert result.final_quantity <= 100


def test_f108_capital_constraint_is_independent() -> None:
    risk = calculate_risk_per_unit(10_000, 9_999, costs())
    result = calculate_position_sizing(auth(100_000), risk, sizing())
    assert result.final_quantity * 10_000 <= 100_000


def test_f108_unauthorized_state_fails_closed() -> None:
    risk = calculate_risk_per_unit(100, 90, costs())
    blocked = auth()
    blocked = replace(blocked, risk_state=RiskState.UNAUTHORIZED)
    with pytest.raises(ValueError, match="Risk authorization"):
        calculate_position_sizing(blocked, risk, sizing())


def test_f108_zero_budget_produces_zero_quantity() -> None:
    risk = calculate_risk_per_unit(100, 90, costs())
    result = calculate_position_sizing(auth(0), risk, sizing())
    assert result.final_quantity == 0
    assert result.reason == "zero_risk_budget"


def test_f108_less_than_one_lot_produces_zero() -> None:
    risk = calculate_risk_per_unit(100, 1, costs())
    result = calculate_position_sizing(auth(10), risk, sizing())
    assert result.final_quantity == 0


def test_f108_increased_risk_budget_cannot_reduce_quantity() -> None:
    risk = calculate_risk_per_unit(100, 90, costs())
    low = calculate_position_sizing(auth(2_000), risk, sizing())
    high = calculate_position_sizing(auth(4_000), risk, sizing())
    assert high.final_quantity >= low.final_quantity
