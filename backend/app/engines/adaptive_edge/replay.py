"""Deterministic causal replay validation for Adaptive Edge."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .e2e import AuditRecord, E2ETrace


EXPECTED_STAGES = (
    "market_event", "feature_snapshot", "prediction", "edge", "economics", "decision",
    "risk_authorization", "instrument", "order_intent", "execution_event", "position",
    "lifecycle",
)


@dataclass(frozen=True)
class ReplayResult:
    deterministic: bool
    stages: tuple[str, ...]
    object_ids: tuple[str, ...]
    reason: str | None = None


def validate_audit_chain(records: Iterable[AuditRecord]) -> ReplayResult:
    records = tuple(records)
    stages = tuple(record.stage for record in records)
    object_ids = tuple(record.object_id for record in records)
    if tuple(record.sequence for record in records) != tuple(range(len(records))):
        return ReplayResult(False, stages, object_ids, "non_contiguous_audit_sequence")
    if stages != EXPECTED_STAGES[: len(stages)]:
        return ReplayResult(False, stages, object_ids, "invalid_causal_stage_order")
    for current, previous in zip(records[1:], records):
        if previous.object_id not in current.parent_ids:
            if not (current.stage == "economics" and previous.stage == "edge"):
                return ReplayResult(False, stages, object_ids, "broken_parent_reference")
    return ReplayResult(True, stages, object_ids)


def replay_trace(trace: E2ETrace) -> ReplayResult:
    """Validate the captured trace without recomputing unresolved strategy math."""
    return validate_audit_chain(trace.audit)
