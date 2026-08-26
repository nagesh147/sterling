from __future__ import annotations

import pytest

from app.engines.adaptive_edge.risk_sizing import (
    ExecutionCostParameters,
    ParameterEstimationMethod,
    ParameterGovernanceError,
    ParameterMetadata,
    ParameterValidationStatus,
    calculate_risk_per_unit,
)


def _param(name: str, value: float, units: str = "INR/unit") -> ParameterMetadata:
    return ParameterMetadata(
        name=name,
        value=value,
        units=units,
        version="test-1",
        provenance="A213",
        estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
        validation_status=ParameterValidationStatus.VALIDATED,
    )


def _costs() -> ExecutionCostParameters:
    return ExecutionCostParameters(
        spread_cost=_param("spread", 1.0),
        expected_slippage=_param("slippage", 0.5),
        brokerage_per_unit=_param("brokerage", 0.1),
        exchange_charges_per_unit=_param("exchange", 0.05),
        taxes_per_unit=_param("taxes", 0.05),
        latency_cost_per_unit=_param("latency", 0.2),
    )


def test_f107_effective_risk_includes_all_execution_friction() -> None:
    result = calculate_risk_per_unit(100.0, 90.0, _costs())
    assert result.valid
    assert result.nominal_risk_per_unit == pytest.approx(10.0)
    assert result.expected_execution_cost_per_unit == pytest.approx(1.9)
    assert result.effective_risk_per_unit == pytest.approx(11.9)


def test_f107_rejects_stop_above_entry() -> None:
    with pytest.raises(ValueError, match="below entry"):
        calculate_risk_per_unit(100.0, 101.0, _costs())


def test_f107_unvalidated_cost_fails_closed() -> None:
    costs = _costs()
    bad = ParameterMetadata(
        name="slippage",
        value=0.5,
        units="INR/unit",
        version="test-1",
        provenance="A213",
        estimation_method=ParameterEstimationMethod.WALK_FORWARD_ESTIMATE,
        validation_status=ParameterValidationStatus.UNRESOLVED,
    )
    costs = ExecutionCostParameters(
        costs.spread_cost,
        bad,
        costs.brokerage_per_unit,
        costs.exchange_charges_per_unit,
        costs.taxes_per_unit,
        costs.latency_cost_per_unit,
    )
    with pytest.raises(ParameterGovernanceError):
        calculate_risk_per_unit(100.0, 90.0, costs)


def test_f107_negative_friction_fails_closed() -> None:
    costs = ExecutionCostParameters(
        _param("spread", -0.1),
        _param("slippage", 0.5),
        _param("brokerage", 0.1),
        _param("exchange", 0.05),
        _param("taxes", 0.05),
        _param("latency", 0.2),
    )
    with pytest.raises(ParameterGovernanceError):
        calculate_risk_per_unit(100.0, 90.0, costs)
