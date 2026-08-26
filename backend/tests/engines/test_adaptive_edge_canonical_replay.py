"""Adversarial and Deterministic Replay Tests for TrueData -> CanonicalMarketEvent -> FeatureSnapshot Boundary."""
from __future__ import annotations

import random
import pytest

from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent, CanonicalEventBoundary
from app.engines.adaptive_edge.feature_engine import FeatureSnapshot, FeatureStatus
from app.engines.adaptive_edge.replay import (
    CanonicalEventSequence,
    event_to_feature_snapshot,
    replay_canonical_sequence,
)
from app.services.providers.truedata.adapter import TrueDataMarketDataAdapter


def make_bar_event(
    record_id: str,
    event_time: str,
    available_at: str,
    close: float = 100.0,
    instrument_id: str = "NIFTY 50",
) -> CanonicalMarketEvent:
    return CanonicalMarketEvent(
        record_id=record_id,
        event_type="bar",
        instrument_id=instrument_id,
        event_time=event_time,
        available_at=available_at,
        source="truedata",
        source_version="2.6",
        payload={
            "open": close - 1.0,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "volume": 1000.0,
            "oi": 500.0,
        },
        provenance={"provider": "TrueData", "feed_type": "historical_bar"},
    )


# 1. Deterministic Replay Twice
def test_replay_same_sequence_twice_produces_identical_outputs():
    e1 = make_bar_event("TD-1", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00", 100.0)
    e2 = make_bar_event("TD-2", "2026-08-14T09:16:00+00:00", "2026-08-14T09:16:00+00:00", 101.0)
    e3 = make_bar_event("TD-3", "2026-08-14T09:17:00+00:00", "2026-08-14T09:17:00+00:00", 102.0)

    seq1 = CanonicalEventSequence.from_events([e1, e2, e3])
    seq2 = CanonicalEventSequence.from_events([e1, e2, e3])

    assert seq1.sequence_hash == seq2.sequence_hash
    assert seq1.events == seq2.events

    snaps1 = replay_canonical_sequence(seq1)
    snaps2 = replay_canonical_sequence(seq2)

    assert len(snaps1) == len(snaps2) == 3
    for s1, s2 in zip(snaps1, snaps2):
        assert s1.snapshot_id == s2.snapshot_id
        assert s1.decision_time == s2.decision_time
        assert s1.observation_cutoff_time == s2.observation_cutoff_time
        assert s1.values == s2.values
        assert s1.statuses == s2.statuses
        assert s1.available_at == s2.available_at
        assert s1.instrument_context == s2.instrument_context


# 2. Out-of-Order Events & Different Arrival Order
def test_shuffled_arrival_order_produces_identical_canonical_ordering_and_hash():
    e1 = make_bar_event("TD-1", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00", 100.0)
    e2 = make_bar_event("TD-2", "2026-08-14T09:16:00+00:00", "2026-08-14T09:16:00+00:00", 101.0)
    e3 = make_bar_event("TD-3", "2026-08-14T09:17:00+00:00", "2026-08-14T09:17:00+00:00", 102.0)

    # In-order arrival
    seq_ordered = CanonicalEventSequence.from_events([e1, e2, e3])
    # Shuffled arrival
    seq_shuffled = CanonicalEventSequence.from_events([e3, e1, e2])

    assert seq_ordered.events == (e1, e2, e3)
    assert seq_shuffled.events == (e1, e2, e3)
    assert seq_ordered.sequence_hash == seq_shuffled.sequence_hash

    snaps_ordered = replay_canonical_sequence(seq_ordered)
    snaps_shuffled = replay_canonical_sequence(seq_shuffled)
    assert snaps_ordered == snaps_shuffled


# 3. Duplicate Events Deduplication
def test_duplicate_events_are_deduplicated_deterministically():
    e1 = make_bar_event("TD-1", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00", 100.0)
    e2 = make_bar_event("TD-2", "2026-08-14T09:16:00+00:00", "2026-08-14T09:16:00+00:00", 101.0)

    # Pass duplicates of e1 and e2
    seq_dups = CanonicalEventSequence.from_events([e1, e2, e1, e2, e1])
    seq_clean = CanonicalEventSequence.from_events([e1, e2])

    assert len(seq_dups.events) == 2
    assert seq_dups.events == (e1, e2)
    assert seq_dups.sequence_hash == seq_clean.sequence_hash


# 4. Equal Timestamps Tie-Breaker
def test_equal_timestamps_sorted_by_record_id_tie_breaker():
    # Same event_time, different record_ids
    e_b = make_bar_event("TD-B", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00", 100.0)
    e_a = make_bar_event("TD-A", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00", 100.0)
    e_c = make_bar_event("TD-C", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00", 100.0)

    seq = CanonicalEventSequence.from_events([e_b, e_c, e_a])
    # Must sort alphabetically by record_id as tie-breaker
    assert [e.record_id for e in seq.events] == ["TD-A", "TD-B", "TD-C"]


# 5. Lookahead Gate: available_at < event_time
def test_available_at_preceding_event_time_is_rejected():
    with pytest.raises(ValueError, match="available_at cannot precede event_time"):
        CanonicalMarketEvent(
            record_id="TD-BAD",
            event_type="bar",
            instrument_id="NIFTY 50",
            event_time="2026-08-14T09:15:00+00:00",
            available_at="2026-08-14T09:14:59+00:00",  # Lookahead!
            source="truedata",
            source_version="2.6",
            payload={"close": 100.0},
        )


def test_sequence_construction_rejects_lookahead_events():
    # Construct invalid event with bypass to test sequence assertion
    bad_evt = make_bar_event("TD-BAD", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00")
    object.__setattr__(bad_evt, "available_at", "2026-08-14T09:14:00+00:00")

    with pytest.raises(ValueError, match="available_at.*cannot precede event_time"):
        CanonicalEventSequence.from_events([bad_evt])


# 6. Missing / Invalid Timestamps
def test_missing_or_invalid_timestamps_are_rejected():
    with pytest.raises(ValueError, match="event_time is required"):
        CanonicalMarketEvent(
            record_id="TD-1",
            event_type="bar",
            instrument_id="NIFTY 50",
            event_time="",
            available_at="2026-08-14T09:15:00+00:00",
            source="truedata",
            source_version="2.6",
            payload={"close": 100.0},
        )

    with pytest.raises(ValueError, match="event_time must be a valid ISO-8601 timestamp"):
        CanonicalMarketEvent(
            record_id="TD-1",
            event_type="bar",
            instrument_id="NIFTY 50",
            event_time="not-a-timestamp",
            available_at="2026-08-14T09:15:00+00:00",
            source="truedata",
            source_version="2.6",
            payload={"close": 100.0},
        )


# 7. Malformed Provider Record
def test_malformed_provider_bar_raises_value_error():
    malformed_bar = {"timestamp": "2026-08-14 09:15:00", "close": "invalid_number"}
    with pytest.raises(ValueError, match="Invalid TrueData bar payload"):
        TrueDataMarketDataAdapter.create_bar_event("NIFTY 50", malformed_bar)


# 8. FeatureSnapshot Integration & Causal Verification
def test_event_to_feature_snapshot_creates_causal_snapshot():
    event = make_bar_event("TD-10", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:01+00:00", close=24500.0)
    snap = event_to_feature_snapshot(event)

    assert isinstance(snap, FeatureSnapshot)
    assert snap.snapshot_id == "SNAP-TD-10"
    assert snap.instrument_context.instrument_id == "NIFTY 50"
    assert snap.decision_time == "2026-08-14T09:15:01+00:00"
    assert snap.observation_cutoff_time == "2026-08-14T09:15:01+00:00"
    assert snap.values["close"] == 24500.0
    assert snap.statuses["close"] == FeatureStatus.VALID
    assert snap.available_at["close"] == "2026-08-14T09:15:01+00:00"
    assert snap.provenance["close"].source_event_ids == ("TD-10",)

    # Causal check does not raise
    snap.assert_causal(snap.decision_time)
