"""F-110 admission boundary: only an admitted risk decision can create an intent."""
from __future__ import annotations

from dataclasses import dataclass

from .f107_f110_pipeline import F107F110Decision
from .order_intent_factory import OrderIntentFactory, OrderIntentInputs


@dataclass(frozen=True)
class F110OrderAdmission:
    admitted: bool
    order_intent: object | None
    reason: str


def create_admitted_order(
    decision: F107F110Decision,
    *,
    selection_id: str,
    side: str,
    intent_version: str,
    created_at: str,
) -> F110OrderAdmission:
    if not decision.admitted:
        return F110OrderAdmission(False, None, f"f110_blocked:{decision.reason}")
    if not decision.instrument_id or decision.sizing is None:
        return F110OrderAdmission(False, None, "f110_missing_authorized_instrument_or_sizing")
    quantity = decision.sizing.final_quantity
    if quantity <= 0:
        return F110OrderAdmission(False, None, "f110_zero_quantity")
    intent = OrderIntentFactory.create(OrderIntentInputs(
        selection_id=selection_id,
        instrument_id=decision.instrument_id,
        side=side,
        quantity=quantity,
        intent_version=intent_version,
        created_at=created_at,
    ))
    return F110OrderAdmission(True, intent, "admitted")
