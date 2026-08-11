"""Source-anchored target/stop mathematics for Adaptive Edge §§33-34.

§33 defines the target/stop competition as argmax ConservativeEV(s,m).
§34 separately defines the conservative-EV gate:

    ConservativeEV <= 0 -> NO_TRADE

No target bounds, probability bounds, minimum samples, calibration rules, or
distributional assumptions are invented here. Candidate inputs are supplied by
upstream validated layers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TargetStopCandidate:
    target: float
    stop: float
    probability_target: float
    expected_gain: float
    probability_stop: float
    expected_loss: float
    costs: float
    conservative_ev: float

    @property
    def expected_value(self) -> float:
        return (
            self.probability_target * self.expected_gain
            - self.probability_stop * self.expected_loss
            - self.costs
        )


@dataclass(frozen=True)
class TargetStopSelection:
    status: str
    candidate: TargetStopCandidate | None


def select_target_stop(candidates: Sequence[TargetStopCandidate]) -> TargetStopSelection:
    """§33: select argmax(ConservativeEV), without applying §34's gate."""
    if not candidates:
        return TargetStopSelection(status="NO_CANDIDATE", candidate=None)
    return TargetStopSelection(
        status="SELECTED",
        candidate=max(candidates, key=lambda candidate: candidate.conservative_ev),
    )


def conservative_ev_eligible(conservative_ev: float) -> bool:
    """§34: conservative EV must be strictly positive for eligibility."""
    return conservative_ev > 0.0
