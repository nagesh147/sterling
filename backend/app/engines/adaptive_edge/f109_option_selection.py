"""Research implementation of the recovered V1.0 F-109 selection rule.

The canonical source selects the eligible option maximizing ExpectedNetEV,
subject to liquidity, slippage, risk, and data-quality constraints. This
module performs only candidate selection; it does not authorize execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class F109Candidate:
    option_symbol: str
    option_type: str
    strike: float
    moneyness: str
    expected_gross_ev: float | None
    execution_cost: float | None
    risk: float | None
    liquidity: float | None
    expected_slippage: float | None
    data_quality: float | None
    required_liquidity: float
    allowable_slippage: float
    max_risk: float
    required_data_quality: float

    @property
    def expected_net_ev(self) -> float | None:
        if self.expected_gross_ev is None or self.execution_cost is None:
            return None
        return self.expected_gross_ev - self.execution_cost


def select_f109(candidates: Iterable[F109Candidate]) -> F109Candidate | None:
    """Return the eligible candidate with maximum ExpectedNetEV.

    Missing economics or constraint inputs fail closed. Ties are resolved by
    canonical lexical option symbol so replay remains deterministic.
    """
    eligible: list[F109Candidate] = []
    for candidate in candidates:
        net_ev = candidate.expected_net_ev
        if net_ev is None:
            continue
        if net_ev <= 0:
            continue
        if candidate.risk is None or candidate.risk > candidate.max_risk:
            continue
        if candidate.liquidity is None or candidate.liquidity < candidate.required_liquidity:
            continue
        if candidate.expected_slippage is None or candidate.expected_slippage > candidate.allowable_slippage:
            continue
        if candidate.data_quality is None or candidate.data_quality < candidate.required_data_quality:
            continue
        eligible.append(candidate)

    if not eligible:
        return None
    return max(eligible, key=lambda c: (c.expected_net_ev or float("-inf"), c.option_symbol))
