"""Deterministic causal replay validation for Adaptive Edge."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .e2e import AuditRecord, E2ETrace


EXPECTED_STAGES = (
    "market_event",
    "feature_snapshot",
    "prediction",
    "edge",
    "economics",
    "decision",
)


@dataclass(frozen=True)
class ReplayResult:
    deterministic: bool
    stages: tuple[str, ...]
    object_ids: tuple[str, ...]
    reason: str | None = None


def validate_audit_chain(records: Iterable[AuditRecord]) -> ReplayResult:
    records = tuple(records)
    if tuple(record.sequence for record in records) != tuple(range(len(records))):
        return ReplayResult(False, tuple(r.stage for r in records), tuple(r.object_id for r in records), "non_contiguous_audit_sequence")

    stages = tuple(record.stage for record in records)
    if stages[: len(EXPECTED_STAGES)] != EXPECTED_STAGES:
        return ReplayResult(False, stages, tuple(r.object_id for r in records), "invalid_causal_stage_order")

    for current, previous in zip(records[1:], records):
        if previous.object_id not in current.parent_ids:
            # Economics intentionally references the edge opportunity itself;
            # every other stage must explicitly reference its immediate parent.
            if not (current.stage == "economics" and previous.stage == "edge"):
                return ReplayResult(False, stages, tuple(r.object_id for r in records), "broken_parent_reference")

    return ReplayResult(True, stages, tuple(r.object_id for r in records))


def replay_trace(trace: E2ETrace) -> ReplayResult:
    """Validate that a captured trace has a replayable causal ordering.

    Replay validation never recalculates unresolved strategy mathematics. It
    verifies that the persisted causal chain is structurally deterministic.
    """
    return validate_audit_chain(trace.audit)
