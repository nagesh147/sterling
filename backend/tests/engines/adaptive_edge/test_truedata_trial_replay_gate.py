from __future__ import annotations

import pytest

from app.engines.adaptive_edge.event_boundary import CanonicalEventBoundary
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.replay import CanonicalEventSequence
from app.services.providers.truedata.adapter import TrueDataMarketDataAdapter
from app.services.providers.truedata.bar_history import bars_to_canonical_sequence
from app.services.providers.truedata.replay_contract import (
    require_causal_order,
    require_truedata_sequence,
)


def _bar(timestamp: str, close: float) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "open": close - 1,
        "high": close + 1,
        "low": close - 2,
        "close": close,
        "volume": 1000,
        "oi": 0,
    }


def test_f101_remains_locked_for_trial_path() -> None:
    assert FORMULAS["F-101"].status is FormulaStatus.LOCKED


def test_truedata_bar_sequence_is_provenance_verified() -> None:
    sequence = bars_to_canonical_sequence(
        "NIFTY-I",
        [
            _bar("2026-08-13 09:16:00", 24701),
            _bar("2026-08-13 09:15:00", 24700),
        ],
    )

    require_truedata_sequence(sequence, "bar")
    require_causal_order(sequence, "bar")
    assert len(sequence.events) == 2
    assert all(event.source == "truedata" for event in sequence.events)
    assert all(event.source_version == "2.6" for event in sequence.events)


def test_truedata_sequence_hash_is_deterministic() -> None:
    rows = [
        _bar("2026-08-13 09:15:00", 24700),
        _bar("2026-08-13 09:16:00", 24701),
    ]
    first = bars_to_canonical_sequence("NIFTY-I", rows)
    second = bars_to_canonical_sequence("NIFTY-I", list(reversed(rows)))

    assert first.sequence_hash == second.sequence_hash


def test_trial_gate_rejects_non_truedata_events() -> None:
    event = CanonicalEventBoundary.create(
        record_id="SYNTH-BAR-1",
        event_type="bar",
        instrument_id="NIFTY-I",
        event_time="2026-08-13T03:45:00+00:00",
        available_at="2026-08-13T03:45:00+00:00",
        source="synthetic",
        source_version="1.0",
        payload={"close": 24700.0},
        source_timestamp="2026-08-13T03:45:00+00:00",
    )

    sequence = CanonicalEventSequence.from_events([event])
    with pytest.raises(ValueError, match="non-TrueData provenance"):
        require_truedata_sequence(sequence, "synthetic")


def test_truedata_adapter_sets_causal_available_at() -> None:
    event = TrueDataMarketDataAdapter.create_bar_event(
        "NIFTY-I",
        _bar("2026-08-13 09:15:00", 24700),
    )

    assert event.source == "truedata"
    assert event.source_version == "2.6"
    assert event.available_at >= event.event_time
