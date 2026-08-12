"""A61 execution-to-accounting integration primitives.

Accounting effects are derived from confirmed fills, never from order intent.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionAccountingError(ValueError):
    """Raised when execution/accounting lineage is invalid."""


class FillStatus(str, Enum):
    CONFIRMED = "confirmed"


@dataclass(frozen=True)
class FillEvent:
    fill_id: str
    intent_id: str
    instrument_id: str
    quantity: int
    price: float
    occurred_at_ms: int
    status: FillStatus = FillStatus.CONFIRMED

    def __post_init__(self) -> None:
        for value, name in ((self.fill_id, "fill_id"), (self.intent_id, "intent_id"), (self.instrument_id, "instrument_id")):
            if not value.strip():
                raise ExecutionAccountingError(f"{name} must not be empty")
        if self.quantity <= 0 or self.price < 0 or self.occurred_at_ms < 0:
            raise ExecutionAccountingError("invalid fill values")


@dataclass(frozen=True)
class PositionEffect:
    effect_id: str
    fill_id: str
    instrument_id: str
    quantity_delta: int
    occurred_at_ms: int


@dataclass(frozen=True)
class AccountingEvent:
    accounting_id: str
    fill_id: str
    position_effect_id: str
    occurred_at_ms: int


def derive_position_effect(fill: FillEvent, quantity_delta: int) -> PositionEffect:
    if fill.status is not FillStatus.CONFIRMED:
        raise ExecutionAccountingError("position effects require confirmed fills")
    if quantity_delta == 0:
        raise ExecutionAccountingError("quantity_delta must be non-zero")
    return PositionEffect(
        effect_id=f"position:{fill.fill_id}",
        fill_id=fill.fill_id,
        instrument_id=fill.instrument_id,
        quantity_delta=quantity_delta,
        occurred_at_ms=fill.occurred_at_ms,
    )


def derive_accounting_event(fill: FillEvent, effect: PositionEffect) -> AccountingEvent:
    if effect.fill_id != fill.fill_id or effect.instrument_id != fill.instrument_id:
        raise ExecutionAccountingError("position effect does not reference the fill")
    if effect.occurred_at_ms < fill.occurred_at_ms:
        raise ExecutionAccountingError("position effect cannot precede fill")
    return AccountingEvent(
        accounting_id=f"accounting:{fill.fill_id}",
        fill_id=fill.fill_id,
        position_effect_id=effect.effect_id,
        occurred_at_ms=effect.occurred_at_ms,
    )
