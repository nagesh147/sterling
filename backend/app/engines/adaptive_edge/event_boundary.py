"""Canonical market-event boundary for Adaptive Edge.

Provider-specific payloads terminate at this boundary. Downstream engine code
consumes only immutable canonical events and never vendor-specific objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping


def _parse_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return parsed


@dataclass(frozen=True)
class CanonicalMarketEvent:
    """Immutable event crossing the external-data boundary.

    `event_time` is the causal market timestamp. `available_at` is the earliest
    timestamp at which the event is permitted to influence downstream logic.
    Provider transport details remain inside `payload` and must be interpreted
    before construction of this object.
    """

    record_id: str
    event_type: str
    instrument_id: str
    event_time: str
    available_at: str
    source: str
    source_version: str
    payload: Mapping[str, Any]
    source_timestamp: str | None = None
    receipt_timestamp: str | None = None
    sequence: int | None = None
    provenance: Mapping[str, str] = MappingProxyType({})

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "event_type",
            "instrument_id",
            "event_time",
            "available_at",
            "source",
            "source_version",
        ):
            value = getattr(self, name)
            if not value:
                raise ValueError(f"{name} is required")

        if self.sequence is not None and self.sequence < 0:
            raise ValueError("sequence must be non-negative")

        event_time = _parse_timestamp(self.event_time, "event_time")
        available_at = _parse_timestamp(self.available_at, "available_at")
        if available_at < event_time:
            raise ValueError("available_at cannot precede event_time")

        for field, value in (
            ("source_timestamp", self.source_timestamp),
            ("receipt_timestamp", self.receipt_timestamp),
        ):
            if value is not None:
                _parse_timestamp(value, field)

        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        object.__setattr__(
            self, "provenance", MappingProxyType(dict(self.provenance))
        )


class CanonicalEventBoundary:
    """Validate and freeze an already-normalized event representation.

    Provider-specific interpretation belongs to the external adapter, not this
    boundary. This class therefore accepts only canonical field names.
    """

    @staticmethod
    def create(
        *,
        record_id: str,
        event_type: str,
        instrument_id: str,
        event_time: str,
        available_at: str,
        source: str,
        source_version: str,
        payload: Mapping[str, Any],
        source_timestamp: str | None = None,
        receipt_timestamp: str | None = None,
        sequence: int | None = None,
        provenance: Mapping[str, str] | None = None,
    ) -> CanonicalMarketEvent:
        return CanonicalMarketEvent(
            record_id=record_id,
            event_type=event_type,
            instrument_id=instrument_id,
            event_time=event_time,
            available_at=available_at,
            source=source,
            source_version=source_version,
            payload=payload,
            source_timestamp=source_timestamp,
            receipt_timestamp=receipt_timestamp,
            sequence=sequence,
            provenance={} if provenance is None else provenance,
        )
