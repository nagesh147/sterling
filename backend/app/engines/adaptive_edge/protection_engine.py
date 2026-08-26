"""Canonical forward-management and backward-profit-protection primitives."""
from __future__ import annotations

from dataclasses import dataclass

from .canonical_math import continuation_value, monotonic_stop, profit_floor, profit_giveback


@dataclass(frozen=True)
class ProtectionState:
    peak_profit: float
    current_profit: float
    giveback: float
    allowed_giveback: float
    floor_price: float
    stop_price: float


def continuation(*, expected_future_profit: float, expected_future_risk: float, expected_future_cost: float) -> float:
    return continuation_value(expected_future_profit, expected_future_risk, expected_future_cost)


def update_protection(
    *,
    peak_profit: float,
    current_profit: float,
    peak_price: float,
    allowed_giveback: float,
    previous_stop: float,
    candidate_dynamic_boundary: float,
    original_risk_boundary: float,
) -> ProtectionState:
    giveback = profit_giveback(peak_profit, current_profit)
    floor_price = profit_floor(peak_price, allowed_giveback)
    candidate = max(original_risk_boundary, floor_price, candidate_dynamic_boundary)
    stop = monotonic_stop(previous_stop, candidate)
    return ProtectionState(
        peak_profit=peak_profit,
        current_profit=current_profit,
        giveback=giveback,
        allowed_giveback=allowed_giveback,
        floor_price=floor_price,
        stop_price=stop,
    )
