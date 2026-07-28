"""Phase 0 regression + unit tests for the Kite-only base-signal adapter.

Freezes the exact `EngineSignalRow` semantics (`source="confluence"`,
`is_active`, `is_fresh`) the adapter depends on, so later Navigator wiring
(Phase 5's scanner join) cannot silently drift from what this file assumes.
"""
from __future__ import annotations

import pytest

from app.engines.navigator.schemas import BaseSignalEvidence, canonical_json_hash
from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineSignalRow
from app.services.navigator.adapters import (
    AdapterError,
    KiteTripleSupertrendAdapter,
    kite_config_revision,
)

_ALIGN = AlignmentChip(fast=1, mid=1, slow=1)
_BAR_CLOSE_MS = 1_753_000_000_000  # arbitrary fixed epoch ms for determinism


def _row(**overrides) -> EngineSignalRow:
    base = dict(
        underlying="NIFTY 50",
        token=256265,
        exchange="NFO",
        regime="BULL",
        alignment=_ALIGN,
        direction="long",
        option_type="CE",
        legs=[],
        spot=24500.0,
        stop_loss=24300.0,
        score=85.0,
        timestamp_ms=_BAR_CLOSE_MS,
        is_active=True,
        is_fresh=True,
        source="spot",
    )
    base.update(overrides)
    return EngineSignalRow(**base)


def _adapt(row: EngineSignalRow, observed_at_ms: int = _BAR_CLOSE_MS + 5_000) -> BaseSignalEvidence:
    return KiteTripleSupertrendAdapter.adapt(
        row,
        user_id="user-1",
        observed_at_ms=observed_at_ms,
        config_revision=kite_config_revision({"trail_target": "fast"}),
    )


class TestFreshAndActiveMapping:
    def test_fresh_row_maps_to_fresh_state(self):
        ev = _adapt(_row(is_fresh=True, is_active=True))
        assert ev.state == "fresh"

    def test_active_only_row_maps_to_active_state(self):
        ev = _adapt(_row(is_fresh=False, is_active=True))
        assert ev.state == "active"

    def test_neither_fresh_nor_active_is_rejected(self):
        with pytest.raises(AdapterError):
            _adapt(_row(is_fresh=False, is_active=False))


class TestSourceProvenancePreserved:
    """Regression: confluence/spot/derivatives source strings must pass through untouched."""

    @pytest.mark.parametrize("source", ["spot", "derivatives", "confluence"])
    def test_source_preserved_verbatim(self, source):
        ev = _adapt(_row(source=source))
        assert ev.source == source

    def test_direction_and_score_preserved(self):
        row = _row(direction="short", score=72.5)
        ev = _adapt(row)
        assert ev.direction == "short"
        assert ev.score_100 == 72.5

    def test_engine_id_is_always_kite_only(self):
        ev = _adapt(_row())
        assert ev.engine_id == "kite_triple_supertrend"


class TestTimingValidation:
    def test_bar_close_after_observation_is_rejected(self):
        with pytest.raises(AdapterError):
            _adapt(_row(timestamp_ms=_BAR_CLOSE_MS), observed_at_ms=_BAR_CLOSE_MS - 1)

    def test_non_positive_timestamp_is_rejected(self):
        with pytest.raises(AdapterError):
            _adapt(_row(timestamp_ms=0))

    def test_bar_open_is_one_hour_before_close(self):
        ev = _adapt(_row())
        assert ev.bar_close_ms - ev.bar_open_ms == 60 * 60 * 1000


class TestScoreBounds:
    def test_score_out_of_bounds_is_rejected(self):
        with pytest.raises(AdapterError):
            _adapt(_row(score=150.0))

    def test_negative_score_is_rejected(self):
        with pytest.raises(AdapterError):
            _adapt(_row(score=-1.0))


class TestHashAndRevisionDeterminism:
    def test_raw_payload_hash_is_deterministic(self):
        ev1 = _adapt(_row())
        ev2 = _adapt(_row())
        assert ev1.raw_payload_hash == ev2.raw_payload_hash

    def test_raw_payload_hash_changes_with_content(self):
        ev1 = _adapt(_row(spot=24500.0))
        ev2 = _adapt(_row(spot=24501.0))
        assert ev1.raw_payload_hash != ev2.raw_payload_hash

    def test_canonical_hash_is_order_independent(self):
        h1 = canonical_json_hash({"a": 1, "b": 2})
        h2 = canonical_json_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_config_revision_changes_with_config_payload(self):
        r1 = kite_config_revision({"trail_target": "fast"})
        r2 = kite_config_revision({"trail_target": "mid"})
        assert r1 != r2

    def test_config_revision_is_stable_for_same_payload(self):
        r1 = kite_config_revision({"trail_target": "fast", "exit_mode": "one_red"})
        r2 = kite_config_revision({"exit_mode": "one_red", "trail_target": "fast"})
        assert r1 == r2


class TestImmutability:
    def test_adapting_does_not_mutate_input_row(self):
        row = _row()
        snapshot = row.model_dump(mode="json")
        _adapt(row)
        assert row.model_dump(mode="json") == snapshot

    def test_evidence_model_is_frozen(self):
        ev = _adapt(_row())
        with pytest.raises(Exception):
            ev.direction = "short"  # type: ignore[misc]
