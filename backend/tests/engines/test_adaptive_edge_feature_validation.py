"""Feature Completeness and Semantic Validation Test Suite for Adaptive Edge."""
from __future__ import annotations

import math
import pytest
from datetime import datetime, timezone

from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.feature_engine import (
    FeatureInput,
    FeatureProvenance,
    FeatureSnapshot,
    FeatureStatus,
    InstrumentContext,
    build_feature_snapshot,
)
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.replay import (
    CanonicalEventSequence,
    event_to_feature_snapshot,
    replay_canonical_sequence,
)


def make_sample_bar_event(
    record_id: str = "TD-BAR-1",
    event_time: str = "2026-08-14T09:15:00+00:00",
    available_at: str = "2026-08-14T09:15:00+00:00",
    open_px: float = 24500.0,
    high_px: float = 24550.0,
    low_px: float = 24480.0,
    close_px: float = 24520.0,
    vol: float = 1250.0,
    oi: float = 50000.0,
) -> CanonicalMarketEvent:
    return CanonicalMarketEvent(
        record_id=record_id,
        event_type="bar",
        instrument_id="NIFTY 50",
        event_time=event_time,
        available_at=available_at,
        source="truedata",
        source_version="2.6",
        payload={
            "open": open_px,
            "high": high_px,
            "low": low_px,
            "close": close_px,
            "volume": vol,
            "oi": oi,
        },
        provenance={"provider": "TrueData", "feed_type": "historical_bar"},
    )


# 1. Complete Valid History Verification
def test_complete_valid_history_populates_feature_snapshot():
    events = [
        make_sample_bar_event("TD-1", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00", close_px=24500.0),
        make_sample_bar_event("TD-2", "2026-08-14T09:16:00+00:00", "2026-08-14T09:16:00+00:00", close_px=24510.0),
        make_sample_bar_event("TD-3", "2026-08-14T09:17:00+00:00", "2026-08-14T09:17:00+00:00", close_px=24525.0),
    ]

    seq = CanonicalEventSequence.from_events(events)
    snapshots = replay_canonical_sequence(seq)

    assert len(snapshots) == 3
    for snap in snapshots:
        assert snap.instrument_context.instrument_id == "NIFTY 50"
        for field_name in ("open", "high", "low", "close", "volume", "oi"):
            assert field_name in snap.values
            assert snap.statuses[field_name] == FeatureStatus.VALID
            assert snap.values[field_name] is not None
            assert snap.available_at[field_name] <= snap.decision_time


# 2. Insufficient History Behavior
def test_insufficient_history_behavior():
    empty_seq = CanonicalEventSequence.from_events([])
    snapshots = replay_canonical_sequence(empty_seq)
    assert snapshots == ()


# 3. Missing Bar Data Handling
def test_missing_bar_fields_handled_gracefully():
    bar_with_missing_oi = CanonicalMarketEvent(
        record_id="TD-MISSING-OI",
        event_type="bar",
        instrument_id="NIFTY 50",
        event_time="2026-08-14T09:15:00+00:00",
        available_at="2026-08-14T09:15:00+00:00",
        source="truedata",
        source_version="2.6",
        payload={
            "open": 24500.0,
            "high": 24550.0,
            "low": 24480.0,
            "close": 24520.0,
            "volume": 1250.0,
            "oi": None,  # Missing field
        },
    )

    snap = event_to_feature_snapshot(bar_with_missing_oi)
    assert snap.values["oi"] is None
    assert snap.statuses["oi"] == FeatureStatus.MISSING
    assert snap.statuses["close"] == FeatureStatus.VALID


# 4. Duplicate Bar Behavior
def test_duplicate_bar_deduplication():
    e1 = make_sample_bar_event("TD-DUP-1", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00")
    e2 = make_sample_bar_event("TD-DUP-1", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00")

    seq = CanonicalEventSequence.from_events([e1, e2])
    assert len(seq.events) == 1
    snapshots = replay_canonical_sequence(seq)
    assert len(snapshots) == 1


# 5. Out-of-Order Input Behavior
def test_out_of_order_input_sorted_canonically():
    e1 = make_sample_bar_event("TD-1", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00", close_px=24500.0)
    e2 = make_sample_bar_event("TD-2", "2026-08-14T09:16:00+00:00", "2026-08-14T09:16:00+00:00", close_px=24510.0)
    e3 = make_sample_bar_event("TD-3", "2026-08-14T09:17:00+00:00", "2026-08-14T09:17:00+00:00", close_px=24520.0)

    # Shuffled input
    seq = CanonicalEventSequence.from_events([e3, e1, e2])
    assert [evt.record_id for evt in seq.events] == ["TD-1", "TD-2", "TD-3"]


# 6. Causality & Timestamp Boundary Check
def test_feature_available_at_must_be_less_than_or_equal_to_decision_time():
    e1 = make_sample_bar_event("TD-1", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:01+00:00")
    snap = event_to_feature_snapshot(e1)

    for feat_name, avail_time in snap.available_at.items():
        assert avail_time <= snap.decision_time


def test_future_lookahead_in_feature_snapshot_is_rejected():
    with pytest.raises(ValueError, match="lookahead detected for feature close"):
        build_feature_snapshot(
            snapshot_id="SNAP-LOOKAHEAD",
            strategy_version="1.0",
            feature_set_version="1.0",
            observation_cutoff_time="2026-08-14T09:15:00+00:00",
            decision_time="2026-08-14T09:15:00+00:00",
            instrument_context=InstrumentContext("NIFTY 50"),
            inputs=[
                FeatureInput(
                    name="close",
                    value=24500.0,
                    available_at="2026-08-14T09:15:01+00:00",  # 1 second after decision_time!
                    status=FeatureStatus.VALID,
                    provenance=FeatureProvenance(source_event_ids=("TD-1",)),
                )
            ],
        )


# 7. Deterministic Replay & Bit-Level Numeric Stability
def test_numeric_determinism_and_bit_stability():
    events = [
        make_sample_bar_event("TD-1", "2026-08-14T09:15:00+00:00", "2026-08-14T09:15:00+00:00", close_px=24500.123456789),
        make_sample_bar_event("TD-2", "2026-08-14T09:16:00+00:00", "2026-08-14T09:16:00+00:00", close_px=24510.987654321),
    ]

    seq1 = CanonicalEventSequence.from_events(events)
    seq2 = CanonicalEventSequence.from_events(events)

    snaps1 = replay_canonical_sequence(seq1)
    snaps2 = replay_canonical_sequence(seq2)

    assert len(snaps1) == len(snaps2) == 2
    for s1, s2 in zip(snaps1, snaps2):
        for k in s1.values:
            val1 = s1.values[k]
            val2 = s2.values[k]
            assert val1 == val2
            if val1 is not None:
                assert math.copysign(1.0, val1) == math.copysign(1.0, val2)


# 8. Specification Gap & Locked Formula Invariant Check
def test_strategy_formulas_remain_locked_and_unimplemented():
    # Formulas F-101 through F-114 must be FormulaStatus.LOCKED
    for f_id in ("F-101", "F-102", "F-103", "F-104", "F-105", "F-106", "F-109", "F-110", "F-111", "F-112", "F-113", "F-114"):
        definition = FORMULAS[f_id]
        assert definition.status == FormulaStatus.LOCKED, f"{f_id} should be LOCKED until specification recovery"
