"""Source-aligned position accounting and protection boundary.

The strategy specification defines PeakPnL and ProfitGiveback as accounting
state. This module does not invent protection thresholds or lifecycle
transitions whose exact strategy definitions are not recovered.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PositionPhase(str, Enum):
    FLAT = "FLAT"
    OPEN = "OPEN"
    PROTECTING = "PROTECTING"
    EXIT_INTENT = "EXIT_INTENT"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class PositionState:
    position_id: str
    phase: PositionPhase
    direction: int
    quantity: float
    entry_price: float
    current_price: float
    stop_price: float | None
    peak_price: float
    realized_pnl: float = 0.0
    peak_profit: float = 0.0


def current_pnl(state: PositionState) -> float:
    return state.realized_pnl + (
        (state.current_price - state.entry_price)
        * state.quantity
        * state.direction
    )


def profit_giveback(state: PositionState) -> float:
    return state.peak_profit - current_pnl(state)


def mark_to_market(state: PositionState, current_price: float) -> PositionState:
    if state.phase in (PositionPhase.FLAT, PositionPhase.CLOSED):
        raise ValueError("cannot mark a flat/closed position")
    if current_price <= 0:
        raise ValueError("current price must be positive")

    updated = PositionState(
        **{
            **state.__dict__,
            "current_price": current_price,
            "peak_price": (
                max(state.peak_price, current_price)
                if state.direction > 0
                else min(state.peak_price, current_price)
            ),
        }
    )
    current = current_pnl(updated)
    return PositionState(
        **{**updated.__dict__, "peak_profit": max(state.peak_profit, current)}
    )


def propose_protection(state: PositionState, candidate_stop: float | None) -> float | None:
    """Apply only the source-defined monotonic protection invariant.

    The exact source defines the candidate-stop relationship separately. This
    function therefore does not invent a threshold, phase transition, or
    protection trigger.
    """
    if state.phase not in (PositionPhase.OPEN, PositionPhase.PROTECTING):
        raise ValueError("protection requires an open position")
    if candidate_stop is None:
        return state.stop_price

    if state.direction > 0:
        if candidate_stop > state.current_price:
            raise ValueError("long stop cannot exceed current price")
        return max(state.stop_price, candidate_stop) if state.stop_price is not None else candidate_stop

    if candidate_stop < state.current_price:
        raise ValueError("short stop cannot be below current price")
    return min(state.stop_price, candidate_stop) if state.stop_price is not None else candidate_stop


def request_exit(state: PositionState) -> PositionPhase:
    """Return the source-defined exit-intent phase without fabricating a trigger."""
    if state.phase in (PositionPhase.FLAT, PositionPhase.CLOSED):
        raise ValueError("cannot exit a flat/closed position")
    return PositionPhase.EXIT_INTENT
