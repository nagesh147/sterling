"""Governed F-107..F-110 bridge from economic eligibility to order admission."""
from __future__ import annotations

from dataclasses import dataclass

from .risk_sizing import ExecutionCostParameters, SizingParameters, calculate_risk_per_unit, calculate_position_sizing
from .f101_f106_contracts import F106OptionCandidate


@dataclass(frozen=True)
class F107F110Input:
    entry_price: float
    initial_stop: float
    authorized_risk_budget: float
    candidate: F106OptionCandidate
    costs: ExecutionCostParameters
    sizing: SizingParameters


@dataclass(frozen=True)
class F107F110Decision:
    admitted: bool
    risk_per_unit: object | None
    sizing: object | None
    instrument_id: str | None
    reason: str


def evaluate_f107_f110(request: F107F110Input) -> F107F110Decision:
    if not request.candidate.eligible:
        return F107F110Decision(False, None, None, None, "f106_candidate_ineligible")
    if request.authorized_risk_budget <= 0:
        return F107F110Decision(False, None, None, None, "invalid_authorized_risk_budget")

    risk = calculate_risk_per_unit(request.entry_price, request.initial_stop, request.costs)
    sizing = calculate_position_sizing(
        risk_per_unit=risk.effective_risk_per_unit,
        authorized_risk_budget=request.authorized_risk_budget,
        entry_price=request.entry_price,
        sizing_params=request.sizing,
    )
    if not risk.valid or not sizing.valid or sizing.final_quantity <= 0:
        return F107F110Decision(False, risk, sizing, None, "risk_sizing_ineligible")
    return F107F110Decision(True, risk, sizing, request.candidate.instrument_id, "admitted")
