"""Strategy-first Adaptive Edge decision boundary.

This module wires source-defined relationships without inventing feature weights,
probability cutoffs, ATR multipliers, or option-selection heuristics. Learned
quantities and candidate distributions enter as explicit inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .canonical_math import (
    ExecutionCost,
    conservative_expected_value,
    expected_net_value,
    expected_value_per_risk,
    target_stop_ev,
)


@dataclass(frozen=True)
class OutcomeEstimate:
    direction: int
    target_probability: float
    expected_gain: float
    stop_probability: float
    expected_loss: float


@dataclass(frozen=True)
class TradeEconomics:
    expected_gross_value: float
    execution_cost: ExecutionCost
    lower_confidence_bound: float
    effective_risk: float

    @property
    def expected_net_value(self) -> float:
        return expected_net_value(self.expected_gross_value, self.execution_cost)

    @property
    def conservative_value(self) -> float:
        return conservative_expected_value(self.lower_confidence_bound)


@dataclass(frozen=True)
class OptionCandidate:
    """A fully evaluated option instrument supplied to the §32 selector.

    The selector deliberately receives validated eligibility flags rather than
    deriving liquidity, slippage, risk, or data-quality thresholds itself.
    Those constraints are learned/validated upstream and remain strategy inputs.
    """

    instrument_id: str
    expected_gross_value: float
    execution_cost: ExecutionCost
    data_ok: bool
    liquidity_ok: bool
    slippage_ok: bool
    risk_ok: bool

    @property
    def expected_net_value(self) -> float:
        return expected_net_value(self.expected_gross_value, self.execution_cost)


@dataclass(frozen=True)
class TargetStopCandidate:
    target_id: str
    stop_id: str
    target_probability: float
    expected_gain: float
    stop_probability: float
    expected_loss: float
    execution_cost: float
    conservative_ev: float


@dataclass(frozen=True)
class Decision:
    actionable: bool
    direction: int
    expected_net_value: float
    conservative_value: float
    value_per_risk: float | None
    target_id: str | None
    stop_id: str | None
    reason: str


def select_option_candidate(
    candidates: Sequence[OptionCandidate],
) -> tuple[OptionCandidate | None, str]:
    """Implement §32: maximize expected net value under validated constraints."""
    if not candidates:
        return None, "no_option_candidates"

    eligible = [
        candidate
        for candidate in candidates
        if candidate.data_ok
        and candidate.liquidity_ok
        and candidate.slippage_ok
        and candidate.risk_ok
    ]
    if not eligible:
        return None, "no_option_candidate_passes_constraints"

    selected = max(eligible, key=lambda candidate: candidate.expected_net_value)
    return selected, "selected_highest_expected_net_value"


def evaluate_candidate(outcome: OutcomeEstimate, economics: TradeEconomics) -> Decision:
    """Apply economic gates only; prediction construction happens upstream."""
    if outcome.direction not in (-1, 1):
        return Decision(False, 0, economics.expected_net_value, economics.conservative_value, None, None, None, "invalid_direction")
    if economics.expected_net_value <= 0:
        return Decision(False, outcome.direction, economics.expected_net_value, economics.conservative_value, None, None, None, "expected_net_value_non_positive")
    if economics.conservative_value <= 0:
        return Decision(False, outcome.direction, economics.expected_net_value, economics.conservative_value, None, None, None, "conservative_ev_non_positive")
    value_per_risk = expected_value_per_risk(economics.conservative_value, economics.effective_risk)
    return Decision(True, outcome.direction, economics.expected_net_value, economics.conservative_value, value_per_risk, None, None, "economically_eligible")


def score_target_stop_candidates(candidates: Sequence[TargetStopCandidate]) -> tuple[TargetStopCandidate | None, str]:
    """Choose the highest conservative EV; do not invent a target/stop threshold."""
    if not candidates:
        return None, "no_target_stop_candidates"
    positive = [candidate for candidate in candidates if candidate.conservative_ev > 0]
    if not positive:
        return None, "no_positive_conservative_ev"
    selected = max(positive, key=lambda candidate: candidate.conservative_ev)
    return selected, "selected_highest_conservative_ev"


def evaluate_target_stop_candidate(candidate: TargetStopCandidate) -> float:
    """Recompute the source EV equation for auditability."""
    return target_stop_ev(
        candidate.target_probability,
        candidate.expected_gain,
        candidate.stop_probability,
        candidate.expected_loss,
        candidate.execution_cost,
    )
