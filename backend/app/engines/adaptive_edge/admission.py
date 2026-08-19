"""Entry admission from recovered invariants.

INV-ENTRY-003 / POSITION INITIATION §65-66:
    at most one active position; same opportunity cannot enter twice.

A177 §21:
    exit != re-entry; a previous authorization cannot be reused.

A126:
    no new entry at or after 14:45 IST.

This is not a re-entry score and not a multi-position PortfolioRisk formula.
F-113 and F-114 remain LOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet

from .e2e import PositionState
from .research_session import a126_session_cutoff_reached


class AdmissionError(ValueError):
    """Raised when a recovered entry invariant blocks admission."""


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    reason: str
    invariants: tuple[str, ...]


def _is_open(position: PositionState | None) -> bool:
    return position is not None and position.quantity > 0


def evaluate_entry_admission(
    *,
    open_position: PositionState | None,
    authorization_id: str,
    opportunity_id: str,
    decision_time: str,
    consumed_authorization_ids: AbstractSet[str] = frozenset(),
    entered_opportunity_ids: AbstractSet[str] = frozenset(),
) -> AdmissionDecision:
    invariants = ("INV-ENTRY-003", "A177", "A126")
    if _is_open(open_position):
        return AdmissionDecision(False, "INV-ENTRY-003_pyramid_blocked", invariants)
    if opportunity_id in entered_opportunity_ids:
        return AdmissionDecision(False, "INV-ENTRY-003_same_opportunity", invariants)
    if authorization_id in consumed_authorization_ids:
        return AdmissionDecision(False, "A177_authorization_reuse_blocked", invariants)
    if a126_session_cutoff_reached(decision_time):
        return AdmissionDecision(False, "A126_session_cutoff_blocks_entry", invariants)
    if not authorization_id or not opportunity_id:
        return AdmissionDecision(False, "INV-ENTRY-002_missing_authorization", invariants)
    return AdmissionDecision(True, "admitted", invariants)


def require_entry_admitted(**kwargs) -> AdmissionDecision:
    decision = evaluate_entry_admission(**kwargs)
    if not decision.admitted:
        raise AdmissionError(decision.reason)
    return decision
