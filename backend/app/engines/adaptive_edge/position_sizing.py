"""A33 position-sizing boundary without inventing a sizing formula."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SizingError(ValueError):
    pass


class SizingStatus(str, Enum):
    SIZED = "SIZED"
    NO_TRADE = "NO_TRADE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    RISK_MEASURE_UNRESOLVED = "RISK_MEASURE_UNRESOLVED"
    CONTRACT_CONSTRAINT_FAILURE = "CONTRACT_CONSTRAINT_FAILURE"
    CAPITAL_CONSTRAINT_FAILURE = "CAPITAL_CONSTRAINT_FAILURE"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    EXPIRED_AUTHORIZATION = "EXPIRED_AUTHORIZATION"


@dataclass(frozen=True)
class QuantityConstraints:
    minimum: int | None = None
    maximum: int | None = None
    increment: int | None = None

    def validate(self, quantity: int) -> None:
        if quantity < 0:
            raise SizingError("quantity must be non-negative")
        if self.minimum is not None and quantity < self.minimum:
            raise SizingError("quantity below minimum")
        if self.maximum is not None and quantity > self.maximum:
            raise SizingError("quantity above maximum")
        if self.increment is not None:
            if self.increment <= 0:
                raise SizingError("quantity increment must be positive")
            if quantity % self.increment != 0:
                raise SizingError("quantity violates increment")


@dataclass(frozen=True)
class SizingRequest:
    authorization_id: str
    opportunity_id: str
    risk_measure_resolved: bool
    contract_constraints: QuantityConstraints
    capital_available: float | None = None
    capital_required: float | None = None

    def __post_init__(self) -> None:
        if not self.authorization_id.strip() or not self.opportunity_id.strip():
            raise SizingError("authorization_id and opportunity_id are required")
        if self.capital_available is not None and self.capital_available < 0:
            raise SizingError("capital_available must be non-negative")
        if self.capital_required is not None and self.capital_required < 0:
            raise SizingError("capital_required must be non-negative")


def validate_candidate_quantity(request: SizingRequest, quantity: int) -> SizingStatus:
    """Validate a supplied candidate; deliberately does not calculate quantity."""
    if not request.risk_measure_resolved:
        return SizingStatus.RISK_MEASURE_UNRESOLVED
    try:
        request.contract_constraints.validate(quantity)
    except SizingError:
        return SizingStatus.INVALID_QUANTITY
    if request.capital_available is not None and request.capital_required is not None:
        if request.capital_required > request.capital_available:
            return SizingStatus.CAPITAL_CONSTRAINT_FAILURE
    if quantity == 0:
        return SizingStatus.NO_TRADE
    return SizingStatus.SIZED
