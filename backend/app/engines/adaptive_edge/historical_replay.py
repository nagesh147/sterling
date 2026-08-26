"""A46 deterministic historical replay/state reconstruction primitives.

A46 reconstructs state from immutable, ordered observations and versioned
inputs. It deliberately does not invent strategy semantics, provider values,
model coefficients, or execution outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Callable, Iterable, TypeVar


class HistoricalReplayError(ValueError):
    """Raised when an A46 replay invariant is violated."""


@dataclass(frozen=True)
class ReplayEvent:
    event_id: str
    observed_at: datetime
    sequence: int
    event_type: str
    payload_fingerprint: str
    source_version: str

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.event_type.strip():
            raise HistoricalReplayError("event identity and type are required")
        if not self.payload_fingerprint.strip() or not self.source_version.strip():
            raise HistoricalReplayError("event fingerprint and source version are required")
        if self.observed_at.tzinfo is None:
            raise HistoricalReplayError("event timestamp must be timezone-aware")
        if self.sequence < 0:
            raise HistoricalReplayError("event sequence cannot be negative")


@dataclass(frozen=True)
class ReplayInputManifest:
    manifest_id: str
    specification_versions: tuple[str, ...]
    feature_snapshot_ids: tuple[str, ...]
    model_state_id: str | None
    event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.manifest_id.strip():
            raise HistoricalReplayError("manifest_id must not be empty")
        if not self.specification_versions:
            raise HistoricalReplayError("at least one specification version is required")
        if not self.event_ids:
            raise HistoricalReplayError("replay manifest requires events")


@dataclass(frozen=True)
class ReplayResult:
    replay_id: str
    manifest_id: str
    state_fingerprint: str
    event_count: int
    first_event_at: datetime
    last_event_at: datetime


StateT = TypeVar("StateT")


def canonical_event_order(events: Iterable[ReplayEvent]) -> tuple[ReplayEvent, ...]:
    """Return a deterministic order and reject ambiguous duplicate sequences."""
    ordered = tuple(sorted(events, key=lambda e: (e.observed_at, e.sequence, e.event_id)))
    seen_sequences: dict[int, ReplayEvent] = {}
    for event in ordered:
        previous = seen_sequences.get(event.sequence)
        if previous is not None and previous.event_id != event.event_id:
            raise HistoricalReplayError(
                f"sequence {event.sequence} is assigned to multiple events"
            )
        seen_sequences[event.sequence] = event
    return ordered


def build_manifest(
    *,
    manifest_id: str,
    specification_versions: Iterable[str],
    feature_snapshot_ids: Iterable[str],
    model_state_id: str | None,
    events: Iterable[ReplayEvent],
) -> ReplayInputManifest:
    ordered = canonical_event_order(events)
    return ReplayInputManifest(
        manifest_id=manifest_id,
        specification_versions=tuple(specification_versions),
        feature_snapshot_ids=tuple(feature_snapshot_ids),
        model_state_id=model_state_id,
        event_ids=tuple(event.event_id for event in ordered),
    )


def replay(
    *,
    replay_id: str,
    manifest: ReplayInputManifest,
    events: Iterable[ReplayEvent],
    initial_state: StateT,
    reducer: Callable[[StateT, ReplayEvent], StateT],
) -> tuple[StateT, ReplayResult]:
    """Replay exactly the events named by the manifest using a supplied reducer."""
    if not replay_id.strip():
        raise HistoricalReplayError("replay_id must not be empty")
    event_list = tuple(events)
    by_id = {event.event_id: event for event in event_list}
    if len(by_id) != len(event_list):
        raise HistoricalReplayError("event IDs must be unique")
    missing = [event_id for event_id in manifest.event_ids if event_id not in by_id]
    if missing:
        raise HistoricalReplayError(f"manifest references missing events: {missing}")
    selected = canonical_event_order(by_id[event_id] for event_id in manifest.event_ids)
    if not selected:
        raise HistoricalReplayError("replay requires at least one event")
    state = initial_state
    for event in selected:
        state = reducer(state, event)
    material = "|".join(
        [
            manifest.manifest_id,
            *manifest.specification_versions,
            *manifest.feature_snapshot_ids,
            manifest.model_state_id or "",
            *(event.event_id + ":" + event.payload_fingerprint for event in selected),
        ]
    )
    fingerprint = sha256(material.encode("utf-8")).hexdigest()
    return state, ReplayResult(
        replay_id=replay_id,
        manifest_id=manifest.manifest_id,
        state_fingerprint=fingerprint,
        event_count=len(selected),
        first_event_at=selected[0].observed_at,
        last_event_at=selected[-1].observed_at,
    )
