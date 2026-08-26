"""Research-only F-103 opportunity eligibility.

F-103 composes already-validated decision gates. It does not invent thresholds
or authorize execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OpportunityAction(str, Enum):
    NO_TRADE = "NO_TRADE"
    BUY_CE = "BUY_CE"
    BUY_PE = "BUY_PE"


@dataclass(frozen=True)
class OpportunityCandidate:
    action: OpportunityAction
    data_ok: bool
    directional_edge_ok: bool
    expected_value: float | None
    conservative_expected_value: float | None
    liquidity_ok: bool
    slippage_ok: bool
    risk_ok: bool


@dataclass(frozen=True)
class OpportunityEligibility:
    eligible: bool
    action: OpportunityAction
    reason: str
    formula_id: str = "F-103"
    formula_version: str = "1.0"


def evaluate_opportunity(candidate: OpportunityCandidate) -> OpportunityEligibility:
    """Apply the V1 mandatory entry gates without adding numeric thresholds."""
    if candidate.action is OpportunityAction.NO_TRADE:
        return OpportunityEligibility(False, OpportunityAction.NO_TRADE, "no_directional_candidate")

    gates = (
        ("data_not_ok", candidate.data_ok),
        ("directional_edge_not_ok", candidate.directional_edge_ok),
        ("missing_expected_value", candidate.expected_value is not None),
        ("expected_value_non_positive", candidate.expected_value is not None and candidate.expected_value > 0),
        (
            "missing_conservative_expected_value",
            candidate.conservative_expected_value is not None,
        ),
        (
            "conservative_expected_value_non_positive",
            candidate.conservative_expected_value is not None
            and candidate.conservative_expected_value > 0,
        ),
        ("liquidity_not_ok", candidate.liquidity_ok),
        ("slippage_not_ok", candidate.slippage_ok),
        ("risk_not_ok", candidate.risk_ok),
    )

    for reason, passed in gates:
        if not passed:
            return OpportunityEligibility(False, OpportunityAction.NO_TRADE, reason)

    return OpportunityEligibility(True, candidate.action, "all_mandatory_gates_passed")
