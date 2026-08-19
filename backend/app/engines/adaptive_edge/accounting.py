"""F-002 Peak P&L and F-003 profit giveback.

Canonical formulas from FORMULAS.md. Anchored, not strategy-specific F-10x.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .risk_sizing import ExecutionCostParameters


@dataclass(frozen=True)
class AccountingSnapshot:
    current_pnl: float
    peak_pnl: float
    profit_giveback: float
    formula_ids: tuple[str, ...] = ("F-002", "F-003")


def peak_pnl(pnl_history: Sequence[float]) -> float:
    if not pnl_history:
        raise ValueError("PeakPnL requires at least one mark")
    return max(pnl_history)


def profit_giveback(peak: float, current: float) -> float:
    return peak - current


def mark_accounting(pnl_history: Sequence[float]) -> AccountingSnapshot:
    current = float(pnl_history[-1])
    peak = peak_pnl(pnl_history)
    return AccountingSnapshot(
        current_pnl=current,
        peak_pnl=peak,
        profit_giveback=profit_giveback(peak, current),
    )


@dataclass(frozen=True)
class RealizedPnlReconciliation:
    """Closed-trade PnL using F-107 execution-cost components.

    Net = Gross - (spread + slippage + brokerage + exchange + taxes + latency)
    applied on each fill leg. Does not invent F-113/F-114 mathematics.
    """

    quantity: int
    side: str
    entry_price: float
    exit_price: float
    legs: int
    gross_pnl: float
    spread_cost: float
    slippage: float
    brokerage: float
    exchange_charges: float
    taxes: float
    latency_cost: float
    execution_cost: float
    net_pnl: float
    formula_ids: tuple[str, ...] = ("F-107",)


def reconcile_realized_pnl(
    *,
    side: str,
    quantity: int,
    entry_price: float,
    exit_price: float,
    cost_params: ExecutionCostParameters,
    legs: int = 2,
) -> RealizedPnlReconciliation:
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if entry_price <= 0 or exit_price <= 0:
        raise ValueError("entry_price and exit_price must be strictly positive")
    if legs <= 0:
        raise ValueError("legs must be positive")
    cost_params.validate_all()

    signed = 1.0 if side == "BUY" else -1.0
    gross = (exit_price - entry_price) * signed * quantity
    scale = float(quantity * legs)
    spread = cost_params.spread_cost.value * scale
    slippage = cost_params.expected_slippage.value * scale
    brokerage = cost_params.brokerage_per_unit.value * scale
    exchange = cost_params.exchange_charges_per_unit.value * scale
    taxes = cost_params.taxes_per_unit.value * scale
    latency = cost_params.latency_cost_per_unit.value * scale
    execution_cost = spread + slippage + brokerage + exchange + taxes + latency
    net = gross - execution_cost
    if execution_cost < 0 or net > gross:
        raise ValueError("realized pnl cost invariant violated")
    return RealizedPnlReconciliation(
        quantity=quantity,
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        legs=legs,
        gross_pnl=gross,
        spread_cost=spread,
        slippage=slippage,
        brokerage=brokerage,
        exchange_charges=exchange,
        taxes=taxes,
        latency_cost=latency,
        execution_cost=execution_cost,
        net_pnl=net,
    )
