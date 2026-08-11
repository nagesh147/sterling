"""Canonical event surface for deterministic replay and causal validation.

This is intentionally separate from the legacy in-process TradeEvent taxonomy
until existing bus consumers are migrated to the stronger event contract.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.domain.primitives import EventEnvelope, Timestamp


class CanonicalEvent(BaseModel):
    """Immutable domain event backed by the canonical event envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    envelope: EventEnvelope

    @property
    def event_id(self) -> str:
        return self.envelope.event_id.value

    @property
    def event_type(self) -> str:
        return self.envelope.event_type

    @property
    def sequence(self) -> int:
        return self.envelope.sequence

    def is_available_at(self, decision_time: Timestamp) -> bool:
        return self.envelope.is_causally_available_at(decision_time)

    def payload_value(self, key: str) -> Any:
        return self.envelope.payload.get(key)
