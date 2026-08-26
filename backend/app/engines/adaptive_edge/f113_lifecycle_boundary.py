"""F-113 post-exit and re-entry boundary; admission math remains locked."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class F113BoundaryDecision:
    allowed: bool
    reason: str

def evaluate_f113_boundary(*, position_is_flat: bool, prior_outcome_finalized: bool, new_signal_valid: bool, risk_authorization_fresh: bool) -> F113BoundaryDecision:
    """Require a completed prior lifecycle and fresh independent authorization."""
    if not position_is_flat:
        return F113BoundaryDecision(False, "position_not_flat")
    if not prior_outcome_finalized:
        return F113BoundaryDecision(False, "prior_outcome_not_finalized")
    if not new_signal_valid:
        return F113BoundaryDecision(False, "new_signal_invalid")
    if not risk_authorization_fresh:
        return F113BoundaryDecision(False, "risk_authorization_not_fresh")
    return F113BoundaryDecision(True, "boundary_conditions_satisfied")
