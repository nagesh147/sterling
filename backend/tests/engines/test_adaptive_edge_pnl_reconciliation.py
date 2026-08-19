"""Exact realized-PnL reconciliation from F-107 cost components.

Gross, itemized costs, and net. No invented F-113/F-114 mathematics.
"""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge.accounting import RealizedPnlReconciliation, reconcile_realized_pnl
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.risk_sizing import (
    ExecutionCostParameters,
    ParameterEstimationMethod,
    ParameterMetadata,
    ParameterValidationStatus,
)


def _param(name: str, value: float) -> ParameterMetadata:
    return ParameterMetadata(
        name=name,
        value=value,
        units="INR",
        version="1.0.0",
        provenance="Master_Spec_v1.0_Sec31_Sec36",
        estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
        validation_status=ParameterValidationStatus.VALIDATED,
    )


def _costs(
    spread: float = 1.0,
    slippage: float = 0.5,
    brokerage: float = 0.2,
    exchange: float = 0.1,
    taxes: float = 0.1,
    latency: float = 0.1,
) -> ExecutionCostParameters:
    return ExecutionCostParameters(
        spread_cost=_param("spread_cost", spread),
        expected_slippage=_param("expected_slippage", slippage),
        brokerage_per_unit=_param("brokerage_per_unit", brokerage),
        exchange_charges_per_unit=_param("exchange_charges_per_unit", exchange),
        taxes_per_unit=_param("taxes_per_unit", taxes),
        latency_cost_per_unit=_param("latency_cost_per_unit", latency),
    )


def test_buy_round_trip_reconciles_gross_costs_and_net():
    rec = reconcile_realized_pnl(
        side="BUY",
        quantity=50,
        entry_price=150.0,
        exit_price=160.0,
        cost_params=_costs(),
    )
    assert rec.gross_pnl == 500.0
    assert rec.spread_cost == 100.0
    assert rec.slippage == 50.0
    assert rec.brokerage == 20.0
    assert rec.exchange_charges == 10.0
    assert rec.taxes == 10.0
    assert rec.latency_cost == 10.0
    assert rec.execution_cost == 200.0
    assert rec.net_pnl == 300.0
    assert rec.net_pnl == rec.gross_pnl - rec.execution_cost
    assert rec.execution_cost == (
        rec.spread_cost + rec.slippage + rec.brokerage + rec.exchange_charges + rec.taxes + rec.latency_cost
    )


def test_sell_round_trip_uses_inverse_gross():
    rec = reconcile_realized_pnl(
        side="SELL",
        quantity=25,
        entry_price=200.0,
        exit_price=180.0,
        cost_params=_costs(),
    )
    assert rec.gross_pnl == 500.0
    assert rec.net_pnl == rec.gross_pnl - rec.execution_cost
    assert rec.net_pnl < rec.gross_pnl


def test_higher_costs_cannot_increase_net_pnl():
    cheap = reconcile_realized_pnl(
        side="BUY", quantity=50, entry_price=150.0, exit_price=160.0, cost_params=_costs(brokerage=0.2)
    )
    dear = reconcile_realized_pnl(
        side="BUY", quantity=50, entry_price=150.0, exit_price=160.0, cost_params=_costs(brokerage=1.2)
    )
    assert dear.net_pnl < cheap.net_pnl
    assert dear.gross_pnl == cheap.gross_pnl


def test_missing_or_invalid_inputs_fail_closed():
    costs = _costs()
    with pytest.raises(ValueError):
        reconcile_realized_pnl(side="HOLD", quantity=50, entry_price=150.0, exit_price=160.0, cost_params=costs)
    with pytest.raises(ValueError):
        reconcile_realized_pnl(side="BUY", quantity=0, entry_price=150.0, exit_price=160.0, cost_params=costs)
    with pytest.raises(ValueError):
        reconcile_realized_pnl(side="BUY", quantity=50, entry_price=0.0, exit_price=160.0, cost_params=costs)
    with pytest.raises(ValueError):
        reconcile_realized_pnl(side="BUY", quantity=50, entry_price=150.0, exit_price=-1.0, cost_params=costs)


def test_f113_f114_remain_locked_and_unresolved():
    assert FORMULAS["F-113"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-114"].status is FormulaStatus.LOCKED
    import app.engines.adaptive_edge as pkg
    assert not hasattr(pkg, "PortfolioRisk")
    assert not hasattr(pkg, "reentry_score")
