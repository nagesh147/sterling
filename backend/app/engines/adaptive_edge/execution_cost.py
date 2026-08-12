"""Provider-neutral execution-cost boundary for Adaptive Edge §31.

The canonical specification defines the additive cost decomposition but does
not define provider-specific distributions or values. This module therefore
accepts explicitly supplied components and performs only the exact additive
aggregation; it never invents missing costs.
"""
from __future__ import annotations

from dataclasses import dataclass


class ExecutionCostError(ValueError):
    """Raised when an execution-cost boundary input is invalid."""


@dataclass(frozen=True)
class ExecutionCostInput:
    """Explicitly supplied execution-cost components in one economic unit.

    Every field is an input rather than a default. A component that is not
    supported by the provider/model must be represented by an explicit value
    supplied by the caller after applicability has been established.
    """

    spread_cost: float
    slippage: float
    brokerage: float
    exchange_charges: float
    taxes: float
    latency_cost: float
    market_impact: float = 0.0

    def __post_init__(self) -> None:
        values = (
            self.spread_cost,
            self.slippage,
            self.brokerage,
            self.exchange_charges,
            self.taxes,
            self.latency_cost,
            self.market_impact,
        )
        if any(value < 0 for value in values):
            raise ExecutionCostError("execution-cost components cannot be negative")

    @property
    def total(self) -> float:
        """Return the canonical additive execution-cost decomposition."""
        return (
            self.spread_cost
            + self.slippage
            + self.brokerage
            + self.exchange_charges
            + self.taxes
            + self.latency_cost
            + self.market_impact
        )
