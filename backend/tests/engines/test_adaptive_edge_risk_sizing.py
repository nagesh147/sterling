"""Unit and governance tests for F-107 Risk-Per-Unit and F-108 Position Sizing."""
import pytest
from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
from app.engines.adaptive_edge.risk_sizing import (
    ExecutionCostParameters,
    ParameterEstimationMethod,
    ParameterGovernanceError,
    ParameterMetadata,
    ParameterValidationStatus,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
)


def make_valid_param(name: str, value: float, units: str = "INR") -> ParameterMetadata:
    return ParameterMetadata(
        name=name,
        value=value,
        units=units,
        version="1.0.0",
        provenance="Master_Spec_v1.0_Sec31_Sec36",
        estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
        validation_status=ParameterValidationStatus.VALIDATED,
    )


def make_valid_cost_params(
    spread: float = 1.0,
    slippage: float = 0.5,
    brokerage: float = 0.2,
    exchange: float = 0.1,
    taxes: float = 0.1,
    latency: float = 0.1,
) -> ExecutionCostParameters:
    return ExecutionCostParameters(
        spread_cost=make_valid_param("spread_cost", spread),
        expected_slippage=make_valid_param("expected_slippage", slippage),
        brokerage_per_unit=make_valid_param("brokerage_per_unit", brokerage),
        exchange_charges_per_unit=make_valid_param("exchange_charges_per_unit", exchange),
        taxes_per_unit=make_valid_param("taxes_per_unit", taxes),
        latency_cost_per_unit=make_valid_param("latency_cost_per_unit", latency),
    )


def make_valid_sizing_params(
    max_qty: float = 500.0, max_cap: float = 100000.0, lot_size: float = 25.0
) -> SizingParameters:
    return SizingParameters(
        max_position_qty=make_valid_param("max_position_qty", max_qty, "contracts"),
        max_capital_allocation=make_valid_param("max_capital_allocation", max_cap, "INR"),
        lot_size=make_valid_param("lot_size", lot_size, "contracts"),
    )


def make_valid_risk_auth(
    authorized_risk: float = 5000.0, state: RiskState = RiskState.AUTHORIZED
) -> RiskAuthorization:
    return RiskAuthorization(
        opportunity_id="opp_123",
        authorized_risk=authorized_risk,
        risk_state=state,
        policy_version="1.0",
        issued_at="2026-08-14T12:00:00Z",
    )


# --- F-107 Tests ---


def test_f107_normal_case():
    costs = make_valid_cost_params(spread=1.0, slippage=0.5, brokerage=0.2, exchange=0.1, taxes=0.1, latency=0.1)
    res = calculate_risk_per_unit(entry_price=100.0, initial_stop=90.0, cost_params=costs)

    assert res.valid is True
    assert res.nominal_risk_per_unit == pytest.approx(10.0)
    assert res.expected_execution_cost_per_unit == pytest.approx(2.0)
    assert res.effective_risk_per_unit == pytest.approx(12.0)
    assert res.formula_id == "F-107"


def test_f107_zero_execution_cost_boundary():
    costs = make_valid_cost_params(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    res = calculate_risk_per_unit(entry_price=100.0, initial_stop=90.0, cost_params=costs)

    assert res.valid is True
    assert res.nominal_risk_per_unit == pytest.approx(10.0)
    assert res.expected_execution_cost_per_unit == pytest.approx(0.0)
    assert res.effective_risk_per_unit == pytest.approx(10.0)


def test_f107_invalid_stop_above_or_equal_entry():
    costs = make_valid_cost_params()

    with pytest.raises(ValueError, match="Initial stop"):
        calculate_risk_per_unit(entry_price=100.0, initial_stop=100.0, cost_params=costs)

    with pytest.raises(ValueError, match="Initial stop"):
        calculate_risk_per_unit(entry_price=100.0, initial_stop=105.0, cost_params=costs)

    res = calculate_risk_per_unit(entry_price=100.0, initial_stop=100.0, cost_params=costs, fail_closed=False)
    assert res.valid is False
    assert res.reason == "non_positive_nominal_risk"


def test_f107_invalid_non_positive_entry_or_stop():
    costs = make_valid_cost_params()

    with pytest.raises(ValueError, match="Entry price"):
        calculate_risk_per_unit(entry_price=0.0, initial_stop=90.0, cost_params=costs)

    with pytest.raises(ValueError, match="Initial stop"):
        calculate_risk_per_unit(entry_price=100.0, initial_stop=0.0, cost_params=costs)


# --- Provenance & Parameter Governance Tests ---


def test_f107_unvalidated_parameter_fails_closed():
    unvalidated_param = ParameterMetadata(
        name="spread_cost",
        value=1.0,
        units="INR",
        version="1.0.0",
        provenance="spec",
        estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
        validation_status=ParameterValidationStatus.UNRESOLVED,
    )
    costs = ExecutionCostParameters(
        spread_cost=unvalidated_param,
        expected_slippage=make_valid_param("slippage", 0.5),
        brokerage_per_unit=make_valid_param("brokerage", 0.2),
        exchange_charges_per_unit=make_valid_param("exchange", 0.1),
        taxes_per_unit=make_valid_param("taxes", 0.1),
        latency_cost_per_unit=make_valid_param("latency", 0.1),
    )

    with pytest.raises(ParameterGovernanceError, match="unvalidated status"):
        calculate_risk_per_unit(entry_price=100.0, initial_stop=90.0, cost_params=costs)

    res = calculate_risk_per_unit(entry_price=100.0, initial_stop=90.0, cost_params=costs, fail_closed=False)
    assert res.valid is False
    assert "parameter_governance_failure" in res.reason


def test_f107_unversioned_parameter_fails_closed():
    unversioned_param = ParameterMetadata(
        name="spread_cost",
        value=1.0,
        units="INR",
        version="",
        provenance="spec",
        estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
        validation_status=ParameterValidationStatus.VALIDATED,
    )
    costs = ExecutionCostParameters(
        spread_cost=unversioned_param,
        expected_slippage=make_valid_param("slippage", 0.5),
        brokerage_per_unit=make_valid_param("brokerage", 0.2),
        exchange_charges_per_unit=make_valid_param("exchange", 0.1),
        taxes_per_unit=make_valid_param("taxes", 0.1),
        latency_cost_per_unit=make_valid_param("latency", 0.1),
    )

    with pytest.raises(ParameterGovernanceError, match="empty version"):
        calculate_risk_per_unit(entry_price=100.0, initial_stop=90.0, cost_params=costs)


# --- F-108 Sizing Tests ---


def test_f108_normal_case():
    costs = make_valid_cost_params(spread=1.0, slippage=1.0, brokerage=0.0, exchange=0.0, taxes=0.0, latency=0.0)
    risk_unit = calculate_risk_per_unit(entry_price=100.0, initial_stop=90.0, cost_params=costs)  # eff_risk = 12.0
    auth = make_valid_risk_auth(authorized_risk=3000.0)
    sizing = make_valid_sizing_params(max_qty=500.0, max_cap=100000.0, lot_size=25.0)

    res = calculate_position_sizing(auth, risk_unit, sizing)

    # 3000 / 12 = 250 contracts; 250 // 25 * 25 = 250
    assert res.valid is True
    assert res.target_quantity_unconstrained == 250
    assert res.final_quantity == 250
    assert res.gross_authorized_risk == pytest.approx(2500.0)  # 10 * 250
    assert res.effective_authorized_risk == pytest.approx(3000.0)  # 12 * 250
    assert res.effective_authorized_risk <= auth.authorized_risk


def test_f108_lot_size_truncation_boundary():
    costs = make_valid_cost_params(spread=0.0, slippage=0.0, brokerage=0.0, exchange=0.0, taxes=0.0, latency=0.0)
    risk_unit = calculate_risk_per_unit(entry_price=100.0, initial_stop=90.0, cost_params=costs)  # eff_risk = 10.0
    auth = make_valid_risk_auth(authorized_risk=2400.0)  # 2400 / 10 = 240
    sizing = make_valid_sizing_params(max_qty=500.0, max_cap=100000.0, lot_size=50.0)

    res = calculate_position_sizing(auth, risk_unit, sizing)

    # 240 // 50 * 50 = 200
    assert res.valid is True
    assert res.target_quantity_unconstrained == 240
    assert res.final_quantity == 200
    assert res.effective_authorized_risk == pytest.approx(2000.0)
    assert res.effective_authorized_risk <= auth.authorized_risk


def test_f108_max_position_cap_bound():
    costs = make_valid_cost_params(spread=0.0, slippage=0.0, brokerage=0.0, exchange=0.0, taxes=0.0, latency=0.0)
    risk_unit = calculate_risk_per_unit(entry_price=100.0, initial_stop=90.0, cost_params=costs)  # eff_risk = 10.0
    auth = make_valid_risk_auth(authorized_risk=10000.0)  # unconstrained = 1000
    sizing = make_valid_sizing_params(max_qty=100.0, max_cap=100000.0, lot_size=25.0)

    res = calculate_position_sizing(auth, risk_unit, sizing)

    assert res.target_quantity_unconstrained == 1000
    assert res.target_quantity_constrained == 100
    assert res.final_quantity == 100


def test_f108_unauthorized_risk_state_fails_closed():
    costs = make_valid_cost_params()
    risk_unit = calculate_risk_per_unit(entry_price=100.0, initial_stop=90.0, cost_params=costs)
    auth = make_valid_risk_auth(authorized_risk=5000.0, state=RiskState.UNAUTHORIZED)
    sizing = make_valid_sizing_params()

    with pytest.raises(ValueError, match="authorization must be in AUTHORIZED"):
        calculate_position_sizing(auth, risk_unit, sizing)

    res = calculate_position_sizing(auth, risk_unit, sizing, fail_closed=False)
    assert res.valid is False
    assert res.final_quantity == 0


def test_f108_zero_authorized_risk_returns_zero_quantity():
    costs = make_valid_cost_params()
    risk_unit = calculate_risk_per_unit(entry_price=100.0, initial_stop=90.0, cost_params=costs)
    auth = make_valid_risk_auth(authorized_risk=0.0)
    sizing = make_valid_sizing_params()

    res = calculate_position_sizing(auth, risk_unit, sizing)

    assert res.valid is True
    assert res.final_quantity == 0
    assert res.effective_authorized_risk == 0.0


# --- Monotonicity and Invariants Tests ---


def test_f107_f108_monotonicity_invariants():
    auth = make_valid_risk_auth(authorized_risk=5000.0)
    sizing = make_valid_sizing_params(max_qty=1000.0, max_cap=100000.0, lot_size=1.0)

    # 1. Increasing execution cost increases effective risk and decreases quantity
    costs_low = make_valid_cost_params(spread=1.0)
    costs_high = make_valid_cost_params(spread=10.0)

    ru_low = calculate_risk_per_unit(100.0, 90.0, costs_low)
    ru_high = calculate_risk_per_unit(100.0, 90.0, costs_high)

    assert ru_high.effective_risk_per_unit > ru_low.effective_risk_per_unit

    sz_low = calculate_position_sizing(auth, ru_low, sizing)
    sz_high = calculate_position_sizing(auth, ru_high, sizing)

    assert sz_high.final_quantity <= sz_low.final_quantity

    # 2. Increasing authorized risk increases quantity
    auth_larger = make_valid_risk_auth(authorized_risk=10000.0)
    sz_larger = calculate_position_sizing(auth_larger, ru_low, sizing)

    assert sz_larger.final_quantity >= sz_low.final_quantity

    # 3. Nominal risk <= Effective risk
    assert ru_low.nominal_risk_per_unit <= ru_low.effective_risk_per_unit
    assert sz_low.gross_authorized_risk <= sz_low.effective_authorized_risk
    assert sz_low.effective_authorized_risk <= auth.authorized_risk


def test_f107_f108_deterministic_replay():
    costs = make_valid_cost_params(spread=1.5, slippage=0.7)
    sizing = make_valid_sizing_params(max_qty=500.0, lot_size=25.0)
    auth = make_valid_risk_auth(authorized_risk=4500.0)

    ru1 = calculate_risk_per_unit(120.0, 105.0, costs)
    sz1 = calculate_position_sizing(auth, ru1, sizing)

    ru2 = calculate_risk_per_unit(120.0, 105.0, costs)
    sz2 = calculate_position_sizing(auth, ru2, sizing)

    assert ru1 == ru2
    assert sz1 == sz2
