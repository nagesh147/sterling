"""Canonical Adaptive Edge accounting operators.

Source: F-002/F-003 in the Adaptive Edge formula registry and strategy anchor.
This module does not derive CurrentPnL. It consumes authoritative CurrentPnL
from execution/accounting state and applies only the source-defined operators.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class AccountingSnapshot:
    current_pnl: float
    peak_pnl: float
    profit_giveback: float


def update_peak_pnl(previous_peak_pnl: float | None, current_pnl: float) -> float:
    """F-002: PeakPnL(t) = max(CurrentPnL(tau)), tau <= t."""
    if not isfinite(current_pnl):
        raise ValueError("current_pnl must be finite")
    if previous_peak_pnl is None:
        return current_pnl
    if not isfinite(previous_peak_pnl):
        raise ValueError("previous_peak_pnl must be finite")
    return max(previous_peak_pnl, current_pnl)


def profit_giveback(peak_pnl: float, current_pnl: float) -> float:
    """F-003: ProfitGiveback(t) = PeakPnL(t) - CurrentPnL(t)."""
    if not isfinite(peak_pnl) or not isfinite(current_pnl):
        raise ValueError("P&L values must be finite")
    return peak_pnl - current_pnl


def snapshot(previous_peak_pnl: float | None, current_pnl: float) -> AccountingSnapshot:
    peak = update_peak_pnl(previous_peak_pnl, current_pnl)
    return AccountingSnapshot(
        current_pnl=current_pnl,
        peak_pnl=peak,
        profit_giveback=profit_giveback(peak, current_pnl),
    )
