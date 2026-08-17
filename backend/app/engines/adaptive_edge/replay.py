from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Sequence

from .e2e import AuditRecord, E2ETrace
from .event_boundary import CanonicalMarketEvent
from .feature_engine import (
    FeatureInput,
    FeatureProvenance,
    FeatureSnapshot,
    FeatureStatus,
    InstrumentContext,
    build_feature_snapshot,
)


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


@dataclass(frozen=True)
class CanonicalEventSequence:
    """Immutable, deterministically sorted sequence of CanonicalMarketEvents."""

    events: tuple[CanonicalMarketEvent, ...]
    sequence_hash: str

    @classmethod
    def from_events(cls, events: Iterable[CanonicalMarketEvent]) -> CanonicalEventSequence:
        seen_records: set[str] = set()
        unique_events: list[CanonicalMarketEvent] = []

        for evt in events:
            if evt.available_at < evt.event_time:
                raise ValueError(
                    f"available_at ({evt.available_at}) cannot precede event_time ({evt.event_time})"
                )
            if evt.record_id in seen_records:
                continue
            seen_records.add(evt.record_id)
            unique_events.append(evt)

        sorted_events = tuple(sorted(unique_events, key=lambda e: (e.event_time, e.record_id)))

        hasher = hashlib.sha256()
        for e in sorted_events:
            payload_str = json.dumps(dict(e.payload), sort_keys=True)
            entry = f"{e.record_id}|{e.event_type}|{e.instrument_id}|{e.event_time}|{e.available_at}|{e.source}|{payload_str}"
            hasher.update(entry.encode("utf-8"))
        seq_hash = hasher.hexdigest()

        return cls(events=sorted_events, sequence_hash=seq_hash)


def event_to_feature_snapshot(
    event: CanonicalMarketEvent,
    *,
    strategy_version: str = "1.0",
    feature_set_version: str = "1.0",
) -> FeatureSnapshot:
    """Bridge a CanonicalMarketEvent to a versioned FeatureSnapshot."""
    inputs: list[FeatureInput] = []
    source_ids = (event.record_id,)

    for key, value in sorted(event.payload.items()):
        if value is None:
            val_float = None
            status = FeatureStatus.MISSING
        else:
            try:
                val_float = float(value)
                status = FeatureStatus.VALID
            except (ValueError, TypeError):
                val_float = None
                status = FeatureStatus.INVALID

        inputs.append(
            FeatureInput(
                name=key,
                value=val_float,
                available_at=event.available_at,
                status=status,
                provenance=FeatureProvenance(source_event_ids=source_ids),
            )
        )

    return build_feature_snapshot(
        snapshot_id=f"SNAP-{event.record_id}",
        strategy_version=strategy_version,
        feature_set_version=feature_set_version,
        observation_cutoff_time=event.available_at,
        decision_time=event.available_at,
        instrument_context=InstrumentContext(instrument_id=event.instrument_id),
        inputs=inputs,
    )


def replay_canonical_sequence(
    sequence: CanonicalEventSequence,
    *,
    strategy_version: str = "1.0",
    feature_set_version: str = "1.0",
) -> tuple[FeatureSnapshot, ...]:
    """Replay a CanonicalEventSequence producing a sequence of FeatureSnapshots."""
    snapshots: list[FeatureSnapshot] = []
    for evt in sequence.events:
        snapshots.append(
            event_to_feature_snapshot(
                evt,
                strategy_version=strategy_version,
                feature_set_version=feature_set_version,
            )
        )
    return tuple(snapshots)
