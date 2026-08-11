"""Source-anchored target/stop evaluation for Adaptive Edge §§33-34.

§33 defines the target/stop competition as argmax ConservativeEV(s,m).
§34 separately defines the conservative-EV gate:

    ConservativeEV <= 0 -> NO_TRADE

This module therefore does not invent target bounds, probability bounds,
minimum samples, calibration rules, or distributional assumptions. Candidate
inputs must already be produced by a validated upstream research layer.
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
    """§33 argmax; §34 positive conservative-EV eligibility."""
    if not candidates:
        return TargetStopSelection(status="NO_TRADE", candidate=None)

    best = max(candidates, key=lambda candidate: candidate.conservative_ev)
    if best.conservative_ev <= 0:
        return TargetStopSelection(status="NO_TRADE", candidate=None)

    return TargetStopSelection(status="SELECTED", candidate=best)
