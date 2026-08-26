"""F-113 structural re-entry admission boundary.

The recovered source does not define a unique numerical re-entry score.
This module therefore enforces only the non-negotiable lifecycle boundary.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReentryContext:
    position_flat: bool
    prior_outcome_finalized: bool
    fresh_signal_valid: bool
    fresh_risk_authorized: bool


@dataclass(frozen=True)
class ReentryDecision:
    admitted: bool
    reason: str


def evaluate_reentry(context: ReentryContext) -> ReentryDecision:
    if not context.position_flat:
        return ReentryDecision(False, "position_not_flat")
    if not context.prior_outcome_finalized:
        return ReentryDecision(False, "prior_outcome_not_finalized")
    if not context.fresh_signal_valid:
        return ReentryDecision(False, "fresh_signal_invalid")
    if not context.fresh_risk_authorized:
        return ReentryDecision(False, "fresh_risk_authorization_missing")
    return ReentryDecision(True, "structural_boundary_satisfied")
