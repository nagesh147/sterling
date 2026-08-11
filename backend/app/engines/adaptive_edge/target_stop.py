"""Target/stop candidate evaluation for Adaptive Edge.

Implements the source-defined §33-34 contract without inventing probability,
calibration, or threshold parameters. Candidate outcome estimates and the
conservative EV are supplied by the validated research layer.

Canonical relationships:

    EV(s,m) = P_target * E[Gain] - P_stop * E[Loss] - Costs
    (s*,m*) = argmax ConservativeEV(s,m)
    ConservativeEV <= 0 -> NO_TRADE

The module is deliberately pure. It does not fit distributions, select
quantiles, or manufacture confidence intervals.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TargetStopCandidate:
    """One validated target/stop candidate at a decision point."""

    target: float
    stop: float
    probability_target: float
    expected_gain: float
    probability_stop: float
    expected_loss: float
    costs: float
    conservative_ev: float

    def validate(self) -> None:
        if self.target <= 0:
            raise ValueError("target must be positive")
        if self.stop <= 0:
            raise ValueError("stop must be positive")
        for name, value in (
            ("probability_target", self.probability_target),
            ("probability_stop", self.probability_stop),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        for name, value in (
            ("expected_gain", self.expected_gain),
            ("expected_loss", self.expected_loss),
            ("costs", self.costs),
            ("conservative_ev", self.conservative_ev),
        ):
            if value < 0 and name in ("expected_gain", "expected_loss", "costs"):
                raise ValueError(f"{name} cannot be negative")

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


def select_target_stop(
    candidates: Sequence[TargetStopCandidate],
) -> TargetStopSelection:
    """Select the candidate with the highest positive conservative EV.

    Candidates with non-positive conservative EV are ineligible. Ties are
    resolved deterministically by preserving input order.
    """
    validated = []
    for candidate in candidates:
        candidate.validate()
        validated.append(candidate)

    if not validated:
        return TargetStopSelection(status="NO_TRADE", candidate=None)

    best = max(validated, key=lambda candidate: candidate.conservative_ev)
    if best.conservative_ev <= 0:
        return TargetStopSelection(status="NO_TRADE", candidate=None)

    return TargetStopSelection(status="SELECTED", candidate=best)
