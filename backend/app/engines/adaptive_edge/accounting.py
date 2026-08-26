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


def update_peak_pnl(previous_peak: float | None, current_pnl: float) -> float:
    """Advance the peak, never retract it.

    The peak is the high-water mark profit giveback is measured against, so it
    ratchets: a mark below the peak leaves it untouched. `None` means no mark
    has been taken yet, and the first one sets the peak.
    """
    if previous_peak is None:
        return float(current_pnl)
    return max(float(previous_peak), float(current_pnl))


def snapshot(peak: float, current: float) -> AccountingSnapshot:
    """Take an accounting snapshot from an already-established peak.

    `mark_accounting` derives the peak from a full history; this takes the peak
    a caller already carries. `current` is authoritative — it is the live mark,
    not re-derived from the peak — so a snapshot whose current exceeds the peak
    passed in reports the giveback as negative rather than quietly clamping.
    """
    return AccountingSnapshot(
        current_pnl=float(current),
        peak_pnl=float(peak),
        profit_giveback=profit_giveback(float(peak), float(current)),
    )


def mark_accounting(pnl_history: Sequence[float]) -> AccountingSnapshot:
    current = float(pnl_history[-1])
    peak = peak_pnl(pnl_history)
    return AccountingSnapshot(
        current_pnl=current,
        peak_pnl=peak,
        profit_giveback=profit_giveback(peak, current),
    )
