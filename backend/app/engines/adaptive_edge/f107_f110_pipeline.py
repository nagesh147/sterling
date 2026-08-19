"""Governed F-107..F-110 bridge from economic eligibility to order admission."""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import RiskAuthorization, RiskState
from .f101_f106_contracts import F106OptionCandidate
from .risk_sizing import (
    ExecutionCostParameters,
    PositionSizingAssessment,
    RiskPerUnitAssessment,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
)


@dataclass(frozen=True)
class F107F110Input:
    entry_price: float
    initial_stop: float
    risk_authorization: RiskAuthorization
    candidate: F106OptionCandidate
    costs: ExecutionCostParameters
    sizing: SizingParameters


@dataclass(frozen=True)
class F107F110Decision:
    admitted: bool
    risk_per_unit: RiskPerUnitAssessment | None
    sizing: PositionSizingAssessment | None
    instrument_id: str | None
    reason: str


def evaluate_f107_f110(request: F107F110Input) -> F107F110Decision:
    if not request.candidate.eligible:
        return F107F110Decision(False, None, None, None, "f106_candidate_ineligible")
    if request.risk_authorization.risk_state not in (RiskState.AUTHORIZED, RiskState.REDUCED):
        return F107F110Decision(False, None, None, None, "risk_not_authorized")
    if request.risk_authorization.authorized_risk <= 0:
        return F107F110Decision(False, None, None, None, "invalid_authorized_risk_budget")

    risk = calculate_risk_per_unit(request.entry_price, request.initial_stop, request.costs)
    sizing = calculate_position_sizing(
        request.risk_authorization,
        risk,
        request.sizing,
    )
    if not risk.valid or not sizing.valid or sizing.final_quantity <= 0:
        return F107F110Decision(False, risk, sizing, None, "risk_sizing_ineligible")
    return F107F110Decision(True, risk, sizing, request.candidate.instrument_id, "admitted")
