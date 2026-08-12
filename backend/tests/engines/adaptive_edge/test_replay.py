from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.replay import (
    ReplayError,
    ReplayEvent,
    ReplayManifest,
    replay,
)

UTC = timezone.utc
T0 = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def event(event_id: str, sequence: int, minute: int = 0) -> ReplayEvent:
    return ReplayEvent(
        event_id=event_id,
        observed_at=T0.replace(minute=minute),
        sequence_number=sequence,
        event_type="OBSERVATION",
        payload_fingerprint=f"payload:{event_id}",
        source_version="source-v1",
    )


def manifest(*event_ids: str, cutoff: datetime | None = None) -> ReplayManifest:
    return ReplayManifest(
        manifest_id="manifest-1",
        specification_versions=("spec-v2",),
        feature_snapshot_ids=("features-1",),
        model_state_id="model-1",
        event_ids=event_ids,
        cutoff=cutoff,
    )


def reducer(state: int, current: ReplayEvent) -> int:
    return state + current.sequence_number


def test_replay_orders_by_observation_time_then_sequence_then_identity():
    result = replay(
        manifest("e2", "e1"),
        (event("e2", 2, 1), event("e1", 1, 0)),
        0,
        reducer,
    )
    assert result.event_ids == ("e1", "e2")
    assert result.state == 3


def test_replay_is_deterministic_for_same_manifest_and_events():
    events = (event("e1", 1), event("e2", 2, 1))
    first = replay(manifest("e1", "e2"), events, 0, reducer)
    second = replay(manifest("e1", "e2"), events, 0, reducer)
    assert first.state == second.state
    assert first.state_fingerprint == second.state_fingerprint
    assert first.replay_fingerprint == second.replay_fingerprint


def test_missing_manifest_event_is_fatal():
    with pytest.raises(ReplayError, match="missing manifest events"):
        replay(manifest("e1", "missing"), (event("e1", 1),), 0, reducer)


def test_duplicate_event_identity_is_fatal():
    with pytest.raises(ReplayError, match="duplicate event identity"):
        replay(manifest("e1"), (event("e1", 1), event("e1", 1)), 0, reducer)


def test_duplicate_sequence_number_is_fatal():
    with pytest.raises(ReplayError, match="duplicate sequence number"):
        replay(manifest("e1", "e2"), (event("e1", 1), event("e2", 1)), 0, reducer)


def test_future_event_cannot_cross_replay_cutoff():
    cutoff = T0.replace(minute=1)
    with pytest.raises(ReplayError, match="after replay cutoff"):
        replay(manifest("e1", "e2", cutoff=cutoff), (event("e1", 1, 0), event("e2", 2, 2)), 0, reducer)


def test_event_identity_and_payload_fingerprint_contribute_to_replay_fingerprint():
    first = replay(manifest("e1"), (event("e1", 1),), 0, reducer)
    changed = ReplayEvent(
        event_id="e1",
        observed_at=T0,
        sequence_number=1,
        event_type="OBSERVATION",
        payload_fingerprint="different-payload",
        source_version="source-v1",
    )
    second = replay(manifest("e1"), (changed,), 0, reducer)
    assert first.replay_fingerprint != second.replay_fingerprint
