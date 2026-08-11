"""Position-management state machine for Adaptive Edge research.

This module deliberately separates strategy state from broker execution state.
It only emits a management decision; it does not place orders or manufacture
fills. Stop/protection state can tighten but cannot loosen.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PositionPhase(str, Enum):
    FLAT = "FLAT"
    OPEN = "OPEN"
    PROTECTED = "PROTECTED"
    EXIT_PENDING = "EXIT_PENDING"
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


@dataclass(frozen=True)
class ManagementDecision:
    position_id: str
    phase: PositionPhase
    stop_price: float | None
    exit_requested: bool
    reason: str


def mark_to_market(state: PositionState, current_price: float) -> PositionState:
    if state.phase in (PositionPhase.FLAT, PositionPhase.CLOSED):
        raise ValueError("cannot mark a flat/closed position")
    if current_price <= 0:
        raise ValueError("current price must be positive")
    peak = max(state.peak_price, current_price) if state.direction > 0 else min(state.peak_price, current_price)
    unrealized = (current_price - state.entry_price) * state.quantity * state.direction
    peak_profit = max(state.peak_profit, unrealized)
    return PositionState(**{**state.__dict__, "current_price": current_price, "peak_price": peak, "peak_profit": peak_profit})


def propose_protection(state: PositionState, candidate_stop: float | None) -> ManagementDecision:
    if state.phase not in (PositionPhase.OPEN, PositionPhase.PROTECTED):
        raise ValueError("protection requires an open position")
    if candidate_stop is None:
        return ManagementDecision(state.position_id, state.phase, state.stop_price, False, "no_candidate")

    if state.direction > 0:
        if candidate_stop > state.current_price:
            raise ValueError("long stop cannot exceed current price")
        if state.stop_price is not None and candidate_stop < state.stop_price:
            candidate_stop = state.stop_price
    else:
        if candidate_stop < state.current_price:
            raise ValueError("short stop cannot be below current price")
        if state.stop_price is not None and candidate_stop > state.stop_price:
            candidate_stop = state.stop_price

    phase = PositionPhase.PROTECTED if state.phase == PositionPhase.PROTECTED or state.peak_profit > 0 else state.phase
    return ManagementDecision(state.position_id, phase, candidate_stop, False, "protection_updated")


def request_exit(state: PositionState, reason: str) -> ManagementDecision:
    if state.phase in (PositionPhase.FLAT, PositionPhase.CLOSED):
        raise ValueError("cannot exit a flat/closed position")
    if not reason.strip():
        raise ValueError("exit reason is required")
    return ManagementDecision(state.position_id, PositionPhase.EXIT_PENDING, state.stop_price, True, reason)
