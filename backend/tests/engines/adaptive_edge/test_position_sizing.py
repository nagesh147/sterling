import pytest

from backend.app.engines.adaptive_edge.position_sizing import (
    QuantityConstraints,
    SizingRequest,
    SizingStatus,
    SizingError,
    validate_candidate_quantity,
)


def request(**kwargs):
    values = dict(
        authorization_id="auth-1",
        opportunity_id="opp-1",
        risk_measure_resolved=True,
        contract_constraints=QuantityConstraints(minimum=1, maximum=100, increment=10),
    )
    values.update(kwargs)
    return SizingRequest(**values)


def test_unresolved_risk_blocks_quantity():
    assert validate_candidate_quantity(request(risk_measure_resolved=False), 10) is SizingStatus.RISK_MEASURE_UNRESOLVED


def test_quantity_increment_is_enforced():
    assert validate_candidate_quantity(request(), 11) is SizingStatus.INVALID_QUANTITY
    assert validate_candidate_quantity(request(), 20) is SizingStatus.SIZED


def test_minimum_and_maximum_are_enforced():
    assert validate_candidate_quantity(request(), 0) is SizingStatus.INVALID_QUANTITY
    assert validate_candidate_quantity(request(), 110) is SizingStatus.INVALID_QUANTITY


def test_capital_failure_is_explicit():
    req = request(capital_available=100, capital_required=101)
    assert validate_candidate_quantity(req, 10) is SizingStatus.CAPITAL_CONSTRAINT_FAILURE


def test_zero_quantity_is_explicit_no_trade():
    req = request(contract_constraints=QuantityConstraints(minimum=0, maximum=100, increment=10))
    assert validate_candidate_quantity(req, 0) is SizingStatus.NO_TRADE


def test_invalid_increment_configuration_fails():
    with pytest.raises(SizingError):
        QuantityConstraints(increment=0).validate(10)
