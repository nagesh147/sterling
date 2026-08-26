from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.historical_replay import (
    HistoricalReplayError,
    ReplayEvent,
    build_manifest,
    canonical_event_order,
    replay,
)


UTC = timezone.utc


def event(event_id: str, sequence: int, second: int, fingerprint: str = "fp") -> ReplayEvent:
    return ReplayEvent(
        event_id=event_id,
        observed_at=datetime(2026, 1, 1, 9, 15, second, tzinfo=UTC),
        sequence=sequence,
        event_type="market_observation",
        payload_fingerprint=fingerprint,
        source_version="truedata-v2.6",
    )


def test_canonical_order_is_deterministic():
    events = (event("b", 1, 1), event("a", 0, 0))
    assert tuple(e.event_id for e in canonical_event_order(events)) == ("a", "b")


def test_duplicate_sequence_is_rejected():
    with pytest.raises(HistoricalReplayError):
        canonical_event_order((event("a", 1, 0), event("b", 1, 1)))


def test_manifest_freezes_event_identity_and_order():
    manifest = build_manifest(
        manifest_id="m1",
        specification_versions=("adaptive-edge-v2",),
        feature_snapshot_ids=("fs1",),
        model_state_id=None,
        events=(event("b", 1, 1), event("a", 0, 0)),
    )
    assert manifest.event_ids == ("a", "b")


def test_replay_is_deterministic_for_same_inputs():
    events = (event("a", 0, 0, "one"), event("b", 1, 1, "two"))
    manifest = build_manifest(
        manifest_id="m1",
        specification_versions=("adaptive-edge-v2",),
        feature_snapshot_ids=("fs1",),
        model_state_id="model1",
        events=events,
    )

    def reducer(state: int, current: ReplayEvent) -> int:
        return state + 1

    _, first = replay(
        replay_id="r1", manifest=manifest, events=events, initial_state=0, reducer=reducer
    )
    _, second = replay(
        replay_id="r2", manifest=manifest, events=events, initial_state=0, reducer=reducer
    )
    assert first.state_fingerprint == second.state_fingerprint
    assert first.event_count == 2


def test_replay_rejects_missing_manifest_event():
    event_a = event("a", 0, 0)
    manifest = build_manifest(
        manifest_id="m1",
        specification_versions=("adaptive-edge-v2",),
        feature_snapshot_ids=("fs1",),
        model_state_id=None,
        events=(event_a,),
    )
    with pytest.raises(HistoricalReplayError, match="missing events"):
        replay(
            replay_id="r1",
            manifest=manifest,
            events=(),
            initial_state=0,
            reducer=lambda state, current: state + 1,
        )


def test_replay_rejects_duplicate_event_identity():
    event_a = event("a", 0, 0)
    manifest = build_manifest(
        manifest_id="m1",
        specification_versions=("adaptive-edge-v2",),
        feature_snapshot_ids=("fs1",),
        model_state_id=None,
        events=(event_a,),
    )
    with pytest.raises(HistoricalReplayError, match="event IDs must be unique"):
        replay(
            replay_id="r1",
            manifest=manifest,
            events=(event_a, event("a", 1, 1, "different")),
            initial_state=0,
            reducer=lambda state, current: state + 1,
        )
