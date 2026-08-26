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

    Every required component is an input rather than a strategy default.
    Market impact is explicitly optional because the canonical specification
    permits it as an additional modeled component; absence means it is not
    part of this particular cost model, not that its value was silently set
    to zero by the strategy.
    """

    spread_cost: float
    slippage: float
    brokerage: float
    exchange_charges: float
    taxes: float
    latency_cost: float
    market_impact: float | None = None

    def __post_init__(self) -> None:
        values = (
            self.spread_cost,
            self.slippage,
            self.brokerage,
            self.exchange_charges,
            self.taxes,
            self.latency_cost,
        )
        if any(value < 0 for value in values):
            raise ExecutionCostError("execution-cost components cannot be negative")
        if self.market_impact is not None and self.market_impact < 0:
            raise ExecutionCostError("market impact cannot be negative")

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
            + (self.market_impact if self.market_impact is not None else 0.0)
        )
