from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Sequence, TypeVar

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


_State = TypeVar("_State")


class ReplayError(RuntimeError):
    """A replay could not be reproduced exactly as its manifest describes.

    Always fatal. A replay that silently skipped a missing event, or folded a
    duplicate in twice, would still produce a number — and that number would be
    reported with the same confidence as a correct one. Refusing is the only
    honest outcome.
    """


@dataclass(frozen=True)
class ReplayEvent:
    """One event, identified well enough to be reproduced bit-for-bit.

    `payload_fingerprint` stands in for the payload itself: replay proves the
    same inputs were seen, and comparing fingerprints does that without the
    replay log having to carry every payload.
    """

    event_id: str
    observed_at: datetime
    sequence_number: int
    event_type: str
    payload_fingerprint: str
    source_version: str


@dataclass(frozen=True)
class ReplayManifest:
    """The authoritative list of what a replay must consume.

    The manifest is fixed before the replay runs, so the set of events is not a
    function of what happened to be available at replay time. `event_ids` is
    exhaustive in both directions: an id that is missing and an event that was
    not asked for are both errors.
    """

    manifest_id: str
    specification_versions: tuple[str, ...]
    feature_snapshot_ids: tuple[str, ...]
    model_state_id: str
    event_ids: tuple[str, ...]
    cutoff: datetime | None = None


@dataclass(frozen=True)
class ReplayRun:
    """The outcome of one replay, with the fingerprints that make it checkable."""

    manifest_id: str
    event_ids: tuple[str, ...]
    state: object
    state_fingerprint: str
    replay_fingerprint: str


def _fingerprint(*parts: str) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        # Length-prefixed so that concatenation cannot be ambiguous: without
        # this, ("ab", "c") and ("a", "bc") would hash identically.
        hasher.update(f"{len(part)}:{part}".encode("utf-8"))
    return hasher.hexdigest()


def replay(
    manifest: ReplayManifest,
    events: Iterable[ReplayEvent],
    initial_state: _State,
    reducer: Callable[[_State, ReplayEvent], _State],
) -> ReplayRun:
    """Fold `events` into a state in a total, manifest-checked order.

    Ordering is (observed_at, sequence_number, event_id). Observation time comes
    first because that is the causal order; the sequence number breaks ties
    within a timestamp; the id breaks any remaining tie so the order is total
    and never depends on the order events were handed in.

    Every failure below is a case where a replay could still produce a plausible
    number from the wrong inputs, which is why each one raises instead of being
    repaired.
    """
    materialized = tuple(events)

    seen: set[str] = set()
    for event in materialized:
        if event.event_id in seen:
            raise ReplayError(
                f"duplicate event identity in replay input: {event.event_id!r}"
            )
        seen.add(event.event_id)

    by_sequence: dict[int, str] = {}
    for event in materialized:
        clash = by_sequence.get(event.sequence_number)
        if clash is not None:
            raise ReplayError(
                f"duplicate sequence number {event.sequence_number} "
                f"shared by {clash!r} and {event.event_id!r}"
            )
        by_sequence[event.sequence_number] = event.event_id

    expected = set(manifest.event_ids)
    missing = sorted(expected - seen)
    if missing:
        raise ReplayError(
            f"missing manifest events for {manifest.manifest_id}: {', '.join(missing)}"
        )
    unexpected = sorted(seen - expected)
    if unexpected:
        raise ReplayError(
            f"events not listed in manifest {manifest.manifest_id}: {', '.join(unexpected)}"
        )

    if manifest.cutoff is not None:
        # Inclusive: an event observed exactly at the cutoff was available at
        # the cutoff. Only strictly later events are from the future.
        late = sorted(
            event.event_id for event in materialized if event.observed_at > manifest.cutoff
        )
        if late:
            raise ReplayError(
                f"events observed after replay cutoff {manifest.cutoff.isoformat()}: "
                f"{', '.join(late)}"
            )

    ordered = tuple(
        sorted(materialized, key=lambda e: (e.observed_at, e.sequence_number, e.event_id))
    )

    state = initial_state
    for event in ordered:
        state = reducer(state, event)

    state_fingerprint = _fingerprint(json.dumps(state, sort_keys=True, default=repr))
    replay_fingerprint = _fingerprint(
        manifest.manifest_id,
        *manifest.specification_versions,
        *manifest.feature_snapshot_ids,
        manifest.model_state_id,
        *(
            part
            for event in ordered
            for part in (
                event.event_id,
                event.observed_at.isoformat(),
                str(event.sequence_number),
                event.event_type,
                event.payload_fingerprint,
                event.source_version,
            )
        ),
        state_fingerprint,
    )

    return ReplayRun(
        manifest_id=manifest.manifest_id,
        event_ids=tuple(event.event_id for event in ordered),
        state=state,
        state_fingerprint=state_fingerprint,
        replay_fingerprint=replay_fingerprint,
    )
