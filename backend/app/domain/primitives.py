"""Canonical foundation types for Sterling's deterministic domain model.

These types intentionally sit below strategy, risk, execution, accounting,
and infrastructure. They contain no I/O and no broker-specific behavior.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


T = TypeVar("T")


class DomainPrimitiveError(ValueError):
    """Raised when a canonical primitive cannot represent the supplied value."""


class Identifier(BaseModel, Generic[T]):
    """Typed immutable identifier.

    The semantic type is supplied by the concrete subclass, preventing an
    InstrumentID and OrderID with the same textual value from being treated as
    interchangeable domain values.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: str

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise DomainPrimitiveError("identifier must not be empty")
        return value

    def __str__(self) -> str:
        return self.value


class InstrumentID(Identifier["InstrumentID"]):
    pass


class EventID(Identifier["EventID"]):
    pass


class OrderID(Identifier["OrderID"]):
    pass


class FillID(Identifier["FillID"]):
    pass


class PositionID(Identifier["PositionID"]):
    pass


class TradeID(Identifier["TradeID"]):
    pass


class DecisionID(Identifier["DecisionID"]):
    pass


class OpportunityID(Identifier["OpportunityID"]):
    pass


class RunID(Identifier["RunID"]):
    pass


def new_identifier(identifier_type: type[Identifier[T]]) -> Identifier[T]:
    """Create a non-deterministic identifier for runtime use."""
    return identifier_type(value=str(uuid4()))


class Timestamp(BaseModel):
    """Absolute UTC timestamp with explicit causal semantics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: datetime

    @field_validator("value")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise DomainPrimitiveError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.value <= other.value


class Duration(BaseModel):
    """Non-negative elapsed duration represented in integer microseconds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    microseconds: int = Field(ge=0)


class Price(BaseModel):
    """Exact decimal price; tick-grid validation belongs to the instrument."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> Decimal:
        try:
            decimal = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise DomainPrimitiveError("invalid price") from exc
        if not decimal.is_finite():
            raise DomainPrimitiveError("price must be finite")
        return decimal


class Quantity(BaseModel):
    """Exact decimal quantity; lot constraints belong to the instrument."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> Decimal:
        try:
            decimal = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise DomainPrimitiveError("invalid quantity") from exc
        if not decimal.is_finite():
            raise DomainPrimitiveError("quantity must be finite")
        return decimal


class Currency(str, Enum):
    INR = "INR"
    USD = "USD"
    EUR = "EUR"


class Money(BaseModel):
    """Exact monetary value with currency as part of semantic identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: Decimal
    currency: Currency

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: object) -> Decimal:
        try:
            decimal = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise DomainPrimitiveError("invalid monetary amount") from exc
        if not decimal.is_finite():
            raise DomainPrimitiveError("monetary amount must be finite")
        return decimal


class Probability(BaseModel):
    """Probability constrained to the closed interval [0, 1]."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> Decimal:
        try:
            decimal = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise DomainPrimitiveError("invalid probability") from exc
        if not decimal.is_finite() or decimal < 0 or decimal > 1:
            raise DomainPrimitiveError("probability must satisfy 0 <= p <= 1")
        return decimal


class Version(BaseModel):
    """Immutable artifact version plus optional content hash."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: str
    content_hash: str | None = None

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise DomainPrimitiveError("version must not be empty")
        return value


class EventEnvelope(BaseModel):
    """Immutable event metadata required for deterministic replay and lineage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: EventID
    event_type: str
    event_time: Timestamp
    received_time: Timestamp
    source: str
    schema_version: Version
    correlation_id: str | None = None
    causation_id: EventID | None = None
    sequence: int = Field(ge=0)
    payload: dict[str, object]

    @field_validator("event_type", "source")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise DomainPrimitiveError("event metadata must not be empty")
        return value

    @field_validator("received_time")
    @classmethod
    def validate_receipt_time(cls, value: Timestamp, info):
        event_time = info.data.get("event_time")
        if event_time is not None and value < event_time:
            raise DomainPrimitiveError("received_time cannot precede event_time")
        return value

    def is_causally_available_at(self, decision_time: Timestamp) -> bool:
        return self.received_time <= decision_time
