"""A46 deterministic historical replay and state reconstruction.

Replay consumes only immutable, versioned events selected by a manifest. It does
not retrieve live provider values or invent unavailable strategy parameters.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Callable, Sequence


class ReplayError(ValueError):
    """Raised when a deterministic replay invariant is violated."""


@dataclass(frozen=True)
class ReplayEvent:
    event_id: str
    observed_at: datetime
    sequence_number: int
    event_type: str
    payload_fingerprint: str
    source_version: str

    def __post_init__(self) -> None:
        for name in ("event_id", "event_type", "payload_fingerprint", "source_version"):
            if not getattr(self, name).strip():
                raise ReplayError(f"{name} must not be empty")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ReplayError("observed_at must be timezone-aware")
        if self.sequence_number < 0:
            raise ReplayError("sequence_number must be non-negative")


@dataclass(frozen=True)
class ReplayManifest:
    manifest_id: str
    specification_versions: tuple[str, ...]
    feature_snapshot_ids: tuple[str, ...]
    model_state_id: str | None
    event_ids: tuple[str, ...]
    cutoff: datetime | None = None

    def __post_init__(self) -> None:
        if not self.manifest_id.strip():
            raise ReplayError("manifest_id must not be empty")
        if any(not value.strip() for value in self.specification_versions):
            raise ReplayError("specification versions must not be empty")
        if any(not value.strip() for value in self.feature_snapshot_ids):
            raise ReplayError("feature snapshot IDs must not be empty")
        if self.model_state_id is not None and not self.model_state_id.strip():
            raise ReplayError("model_state_id must not be empty when supplied")
        if any(not value.strip() for value in self.event_ids):
            raise ReplayError("event IDs must not be empty")
        if len(set(self.event_ids)) != len(self.event_ids):
            raise ReplayError("manifest event IDs must be unique")
        if self.cutoff is not None and (
            self.cutoff.tzinfo is None or self.cutoff.utcoffset() is None
        ):
            raise ReplayError("cutoff must be timezone-aware")


@dataclass(frozen=True)
class ReplayResult:
    state: object
    state_fingerprint: str
    replay_fingerprint: str
    event_ids: tuple[str, ...]


def _canonical_fingerprint(value: object) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    except (TypeError, ValueError) as exc:
        raise ReplayError("value is not deterministically serializable") from exc
    return sha256(encoded).hexdigest()


def _select_events(
    manifest: ReplayManifest,
    events: Sequence[ReplayEvent],
) -> tuple[ReplayEvent, ...]:
    by_id: dict[str, ReplayEvent] = {}
    for event in events:
        if event.event_id in by_id:
            raise ReplayError(f"duplicate event identity: {event.event_id}")
        by_id[event.event_id] = event

    missing = [event_id for event_id in manifest.event_ids if event_id not in by_id]
    if missing:
        raise ReplayError("missing manifest events: " + ", ".join(missing))

    selected = [by_id[event_id] for event_id in manifest.event_ids]
    if manifest.cutoff is not None:
        future = [event.event_id for event in selected if event.observed_at > manifest.cutoff]
        if future:
            raise ReplayError("events after replay cutoff: " + ", ".join(future))

    sequence_numbers = [event.sequence_number for event in selected]
    if len(sequence_numbers) != len(set(sequence_numbers)):
        raise ReplayError("ambiguous ordering: duplicate sequence number")

    return tuple(sorted(selected, key=lambda e: (e.observed_at, e.sequence_number, e.event_id)))


def replay(
    manifest: ReplayManifest,
    events: Sequence[ReplayEvent],
    initial_state: object,
    reducer: Callable[[object, ReplayEvent], object],
) -> ReplayResult:
    """Reconstruct state from exactly the immutable events named by manifest."""
    ordered = _select_events(manifest, events)
    state = initial_state
    fingerprint_parts: list[object] = [
        manifest.manifest_id,
        manifest.specification_versions,
        manifest.feature_snapshot_ids,
        manifest.model_state_id,
    ]

    for event in ordered:
        state = reducer(state, event)
        fingerprint_parts.append(
            {
                "event_id": event.event_id,
                "observed_at": event.observed_at.isoformat(),
                "sequence_number": event.sequence_number,
                "event_type": event.event_type,
                "payload_fingerprint": event.payload_fingerprint,
                "source_version": event.source_version,
            }
        )

    return ReplayResult(
        state=state,
        state_fingerprint=_canonical_fingerprint(state),
        replay_fingerprint=_canonical_fingerprint(fingerprint_parts),
        event_ids=tuple(event.event_id for event in ordered),
    )
