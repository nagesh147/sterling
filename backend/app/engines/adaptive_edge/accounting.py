"""F-002 Peak P&L and F-003 profit giveback.

Canonical formulas from FORMULAS.md. Anchored, not strategy-specific F-10x.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


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
