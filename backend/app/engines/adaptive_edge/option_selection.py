"""Option selection for Adaptive Edge, anchored to Master Specification §32.

The strategy selects the execution instrument only after the underlying market
state has supplied the primary directional evidence. This module does not
invent liquidity, slippage, risk, or data-quality thresholds; those are
validated inputs supplied by upstream research/execution components.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class OptionCandidate:
    instrument: str
    expected_net_ev: float
    liquidity_ok: bool
    slippage_ok: bool
    risk_ok: bool
    data_quality_ok: bool

    def eligible(self) -> bool:
        return (
            self.liquidity_ok
            and self.slippage_ok
            and self.risk_ok
            and self.data_quality_ok
            and self.expected_net_ev > 0.0
        )


@dataclass(frozen=True)
class OptionSelection:
    status: str
    candidate: OptionCandidate | None


def select_option(candidates: Sequence[OptionCandidate]) -> OptionSelection:
    """§32: O* = argmax ExpectedNetEV_i subject to validated constraints."""
    eligible = [candidate for candidate in candidates if candidate.eligible()]
    if not eligible:
        return OptionSelection(status="NO_TRADE", candidate=None)
    return OptionSelection(
        status="SELECTED",
        candidate=max(eligible, key=lambda candidate: candidate.expected_net_ev),
    )
