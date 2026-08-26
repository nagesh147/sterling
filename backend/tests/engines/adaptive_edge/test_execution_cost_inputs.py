import pytest

from backend.app.engines.adaptive_edge.execution_cost_inputs import (
    ExecutionCostInputError,
    ExecutionCostInputs,
    FreshnessState,
    PriceObservation,
    PriceType,
)


def obs(price_type=PriceType.REFERENCE, **kwargs):
    values = dict(
        instrument_id="NIFTY-OPT-1",
        price_type=price_type,
        value=100.0,
        observation_timestamp_ms=100,
        availability_timestamp_ms=100,
        source="truedata",
        source_version="2.6",
        freshness=FreshnessState.FRESH,
    )
    values.update(kwargs)
    return PriceObservation(**values)


def test_pre_trade_inputs_are_causally_bounded():
    inputs = ExecutionCostInputs("NIFTY-OPT-1", 100, reference_price=obs())
    inputs.validate_pre_trade()


def test_future_observation_is_rejected():
    inputs = ExecutionCostInputs(
        "NIFTY-OPT-1", 100, reference_price=obs(availability_timestamp_ms=101)
    )
    with pytest.raises(ExecutionCostInputError):
        inputs.validate_pre_trade()


def test_fill_is_not_a_pre_trade_input():
    inputs = ExecutionCostInputs("NIFTY-OPT-1", 100, reference_price=obs(PriceType.FILL))
    with pytest.raises(ExecutionCostInputError):
        inputs.validate_pre_trade()


def test_mismatched_instrument_is_rejected():
    inputs = ExecutionCostInputs("NIFTY-OPT-1", 100, bid=obs(instrument_id="OTHER"))
    with pytest.raises(ExecutionCostInputError):
        inputs.validate_pre_trade()


def test_price_observation_requires_provenance():
    with pytest.raises(ExecutionCostInputError):
        obs(source="")


def test_boundary_contains_no_cost_formula():
    inputs = ExecutionCostInputs("NIFTY-OPT-1", 100, bid=obs(), ask=obs())
    assert inputs.available_for_pre_trade()
    # The boundary represents inputs only; it intentionally has no cost value.
