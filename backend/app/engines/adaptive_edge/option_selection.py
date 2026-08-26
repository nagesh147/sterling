"""Option selection for Adaptive Edge §32.

The source-defined §32 operation is only:

    O* = argmax ExpectedNetEV_i

subject to validated liquidity, slippage, risk and data-quality constraints.
The positive conservative-EV eligibility gate belongs to the downstream
entry/trade objective (§34-35 and §66), not to the §32 argmax itself.
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

    def eligible_for_selection(self) -> bool:
        return (
            self.liquidity_ok
            and self.slippage_ok
            and self.risk_ok
            and self.data_quality_ok
        )


@dataclass(frozen=True)
class OptionSelection:
    status: str
    candidate: OptionCandidate | None


def select_option(candidates: Sequence[OptionCandidate]) -> OptionSelection:
    """§32: select argmax(ExpectedNetEV) subject to validated constraints."""
    eligible = [candidate for candidate in candidates if candidate.eligible_for_selection()]
    if not eligible:
        return OptionSelection(status="NO_CANDIDATE", candidate=None)
    return OptionSelection(
        status="SELECTED",
        candidate=max(eligible, key=lambda candidate: candidate.expected_net_ev),
    )
