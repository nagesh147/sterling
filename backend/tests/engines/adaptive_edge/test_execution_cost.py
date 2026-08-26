import pytest

from backend.app.engines.adaptive_edge.execution_cost import (
    ExecutionCostError,
    ExecutionCostInput,
)


def test_execution_cost_is_exact_additive_decomposition() -> None:
    cost = ExecutionCostInput(
        spread_cost=1.0,
        slippage=2.0,
        brokerage=3.0,
        exchange_charges=4.0,
        taxes=5.0,
        latency_cost=6.0,
        market_impact=7.0,
    )

    assert cost.total == pytest.approx(28.0)


def test_market_impact_is_not_silently_invented() -> None:
    cost = ExecutionCostInput(
        spread_cost=1.0,
        slippage=2.0,
        brokerage=3.0,
        exchange_charges=4.0,
        taxes=5.0,
        latency_cost=6.0,
    )

    assert cost.market_impact is None
    assert cost.total == pytest.approx(21.0)


def test_negative_cost_component_is_rejected() -> None:
    with pytest.raises(ExecutionCostError, match="cannot be negative"):
        ExecutionCostInput(
            spread_cost=-1.0,
            slippage=0.0,
            brokerage=0.0,
            exchange_charges=0.0,
            taxes=0.0,
            latency_cost=0.0,
        )


def test_negative_market_impact_is_rejected() -> None:
    with pytest.raises(ExecutionCostError, match="cannot be negative"):
        ExecutionCostInput(
            spread_cost=0.0,
            slippage=0.0,
            brokerage=0.0,
            exchange_charges=0.0,
            taxes=0.0,
            latency_cost=0.0,
            market_impact=-1.0,
        )
