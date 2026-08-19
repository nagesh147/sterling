from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .execution_adapter import CanonicalExecutionEvent, CanonicalExecutionStatus

DEFAULT_BROKER_STATUS_MAP: dict[str, CanonicalExecutionStatus] = {
    "SUBMITTED": CanonicalExecutionStatus.SUBMITTED,
    "ACKNOWLEDGED": CanonicalExecutionStatus.ACKNOWLEDGED,
    "PARTIALLY_FILLED": CanonicalExecutionStatus.PARTIALLY_FILLED,
    "FILLED": CanonicalExecutionStatus.FILLED,
    "REJECTED": CanonicalExecutionStatus.REJECTED,
    "CANCELLED": CanonicalExecutionStatus.CANCELLED,
    "CANCEL_REQUESTED": CanonicalExecutionStatus.CANCEL_REQUESTED,
    "EXPIRED": CanonicalExecutionStatus.EXPIRED,
    "AMENDED": CanonicalExecutionStatus.AMENDED,
}


@dataclass(frozen=True)
class BrokerExecutionEvent:
    broker_event_id: str
    order_intent_id: str
    broker_status: str
    event_time: str
    broker_reference: str | None = None
    filled_quantity: int = 0
    fill_price: float | None = None
    receipt_time: str | None = None


class BrokerEventMapper:
    """Translate explicitly declared broker statuses into canonical states.

    Unknown provider values fail closed to UNKNOWN. No fuzzy matching or
    undocumented inference is permitted.
    """

    def __init__(self, status_map: Mapping[str, CanonicalExecutionStatus]):
        self._status_map = dict(status_map)

    def map(self, event: BrokerExecutionEvent) -> CanonicalExecutionEvent:
        status = self._status_map.get(event.broker_status, CanonicalExecutionStatus.UNKNOWN)
        return CanonicalExecutionEvent(
            execution_event_id=event.broker_event_id,
            order_intent_id=event.order_intent_id,
            event_type=status,
            event_time=event.event_time,
            broker_reference=event.broker_reference,
            filled_quantity=event.filled_quantity,
            fill_price=event.fill_price,
            evidence_class="OBSERVED",
            receipt_time=event.receipt_time,
        )
