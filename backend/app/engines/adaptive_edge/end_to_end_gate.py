"""A60 end-to-end causal and safety invariant gate."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class EndToEndGateError(ValueError):
    """Raised when the complete Adaptive Edge chain violates an invariant."""


class ChainStage(str, Enum):
    OBSERVATION = "observation"
    FEATURE_SNAPSHOT = "feature_snapshot"
    PREDICTION = "prediction"
    ECONOMIC_DECISION = "economic_decision"
    RISK_AUTHORIZATION = "risk_authorization"
    OPERATIONAL_AUTHORIZATION = "operational_authorization"
    EXECUTION_AUTHORIZATION = "execution_authorization"
    ORDER_INTENT = "order_intent"
    SUBMISSION = "submission"
    FILL = "fill"
    ACCOUNTING = "accounting"
    AUDIT = "audit"


@dataclass(frozen=True)
class ChainEvent:
    stage: ChainStage
    event_id: str
    occurred_at_ms: int
    causal_parent_id: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise EndToEndGateError("event_id is required")
        if self.occurred_at_ms < 0:
            raise EndToEndGateError("occurred_at_ms must be non-negative")


REQUIRED_ORDER: Tuple[ChainStage, ...] = tuple(ChainStage)


def validate_causal_chain(events: Tuple[ChainEvent, ...]) -> None:
    """Validate ordering and causal references without inventing strategy policy."""
    if len(events) != len(REQUIRED_ORDER):
        raise EndToEndGateError("complete chain is required")
    if tuple(event.stage for event in events) != REQUIRED_ORDER:
        raise EndToEndGateError("chain stages are incomplete or out of order")
    for index, event in enumerate(events):
        if index == 0:
            if event.causal_parent_id is not None:
                raise EndToEndGateError("root observation cannot have a causal parent")
            continue
        parent = events[index - 1]
        if event.causal_parent_id != parent.event_id:
            raise EndToEndGateError("each stage must reference the immediately preceding causal event")
        if event.occurred_at_ms < parent.occurred_at_ms:
            raise EndToEndGateError("causal time cannot move backward")


def validate_no_execution_without_authorization(events: Tuple[ChainEvent, ...]) -> None:
    validate_causal_chain(events)
    execution_index = next(i for i, event in enumerate(events) if event.stage is ChainStage.ORDER_INTENT)
    required = {ChainStage.RISK_AUTHORIZATION, ChainStage.OPERATIONAL_AUTHORIZATION, ChainStage.EXECUTION_AUTHORIZATION}
    observed = {event.stage for event in events[:execution_index]}
    if not required.issubset(observed):
        raise EndToEndGateError("order intent requires risk, operational, and execution authorization")
