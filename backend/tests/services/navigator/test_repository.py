"""Phase 1 tests for the low-level Navigator storage primitives: uniqueness/
idempotency guarantees, cursor pagination, and the fail-closed contract when
the SQLite store is unavailable (spec §14, §20.7)."""
from __future__ import annotations

import os
import tempfile

import pytest

from app.services import db
from app.services.navigator import repository as repo
from app.services.navigator.repository import NavigatorStorageError


@pytest.fixture(autouse=True)
def isolated_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    yield
    os.unlink(path)


def _snapshot(**overrides) -> dict:
    base = dict(
        account_scope="acct-1", underlying="NIFTY 50", spot_token=256265, spot=24500.0,
        exchange="NFO", expiry="2026-08-06", instrument_token=111, tradingsymbol="NIFTY26AUG24500CE",
        option_type="CE", strike=24500.0, lot_size=75, tick_size=0.05, bid=100.0, ask=101.0,
        last_price=100.5, mid=100.5, implied_volatility=0.15, open_interest=1000,
        cumulative_volume=5000, exchange_timestamp_ms=1_753_000_000_000, received_at_ms=1_753_000_000_100,
        sample_bucket_ms=1_753_000_000_000, quote_quality="ok", config_revision=1,
    )
    base.update(overrides)
    return base


def _feature_snapshot(**overrides) -> dict:
    base = dict(
        user_id="user-1", underlying="NIFTY 50", timeframe="60minute",
        bar_close_ms=1_753_000_000_000, observed_at_ms=1_753_000_005_000,
        config_revision=1, model_versions_json="{}", quality="ok",
        avwap_json=None, range_json=None, volatility_json=None, flow_json=None,
        gamma_json=None, input_hash="hash-1",
    )
    base.update(overrides)
    return base


def _signal_event(**overrides) -> dict:
    base = dict(
        decision_id="dec-1", user_id="user-1", underlying="NIFTY 50",
        bar_close_ms=1_753_000_000_000, generated_at_ms=1_753_000_005_000,
        direction="long", status="CONFIRMED", effective_score=80.0,
        execution_eligible=0, config_revision=1, payload_json="{}",
    )
    base.update(overrides)
    return base


class TestOptionSnapshotUniqueness:
    def test_insert_then_duplicate_is_ignored(self):
        assert repo.insert_option_snapshot(_snapshot()) is True
        assert repo.insert_option_snapshot(_snapshot()) is False  # same (scope, token, bucket)

    def test_different_bucket_is_a_new_row(self):
        repo.insert_option_snapshot(_snapshot())
        assert repo.insert_option_snapshot(_snapshot(sample_bucket_ms=1_753_000_060_000)) is True

    def test_fetch_returns_rows_since_bucket(self):
        repo.insert_option_snapshot(_snapshot(sample_bucket_ms=100))
        repo.insert_option_snapshot(_snapshot(sample_bucket_ms=200))
        rows = repo.fetch_option_snapshots("acct-1", "NIFTY 50", "2026-08-06", since_bucket_ms=150)
        assert [r["sample_bucket_ms"] for r in rows] == [200]


class TestFeatureSnapshotIdempotency:
    def test_replaying_identical_inputs_does_not_duplicate(self):
        assert repo.insert_feature_snapshot(_feature_snapshot()) is True
        assert repo.insert_feature_snapshot(_feature_snapshot()) is False

    def test_different_input_hash_is_a_new_row(self):
        repo.insert_feature_snapshot(_feature_snapshot())
        assert repo.insert_feature_snapshot(_feature_snapshot(input_hash="hash-2")) is True


class TestSignalEventImmutability:
    def test_duplicate_decision_id_is_ignored_not_overwritten(self):
        assert repo.insert_signal_event(_signal_event(effective_score=80.0)) is True
        assert repo.insert_signal_event(_signal_event(effective_score=999.0)) is False
        stored = repo.fetch_signal_event("dec-1")
        assert stored["effective_score"] == 80.0  # the "corrected" 999 never applied

    def test_pagination_is_newest_first_and_cursors_correctly(self):
        for i in range(5):
            repo.insert_signal_event(_signal_event(
                decision_id=f"dec-{i}", generated_at_ms=1000 + i,
            ))
        page1 = repo.fetch_signal_events_page("user-1", limit=2)
        assert [e["decision_id"] for e in page1] == ["dec-4", "dec-3"]
        page2 = repo.fetch_signal_events_page(
            "user-1", limit=2, before_generated_at_ms=page1[-1]["generated_at_ms"]
        )
        assert [e["decision_id"] for e in page2] == ["dec-2", "dec-1"]

    def test_pagination_filters_by_underlying(self):
        repo.insert_signal_event(_signal_event(decision_id="a", underlying="NIFTY 50", generated_at_ms=1))
        repo.insert_signal_event(_signal_event(decision_id="b", underlying="NIFTY BANK", generated_at_ms=2))
        rows = repo.fetch_signal_events_page("user-1", underlying="NIFTY BANK")
        assert [e["decision_id"] for e in rows] == ["b"]

    def test_pagination_is_tie_safe_when_many_rows_share_one_timestamp(self):
        # A whole scan's worth of decisions legitimately share one
        # generated_at_ms. Paging on that column alone would silently drop
        # whatever's left of the tied group once a page boundary lands
        # inside it — the cursor must also carry decision_id.
        for i in range(5):
            repo.insert_signal_event(_signal_event(decision_id=f"tied-{i}", generated_at_ms=5000))
        page1 = repo.fetch_signal_events_page("user-1", limit=2)
        assert len(page1) == 2
        page2 = repo.fetch_signal_events_page(
            "user-1", limit=2,
            before_generated_at_ms=page1[-1]["generated_at_ms"], before_decision_id=page1[-1]["decision_id"],
        )
        page3 = repo.fetch_signal_events_page(
            "user-1", limit=2,
            before_generated_at_ms=page2[-1]["generated_at_ms"], before_decision_id=page2[-1]["decision_id"],
        )
        seen = [e["decision_id"] for e in page1 + page2 + page3]
        assert sorted(seen) == [f"tied-{i}" for i in range(5)]  # every tied row surfaced exactly once


class TestCalibrationState:
    def test_insert_and_fetch_latest(self):
        repo.insert_calibration_state(dict(
            user_id="user-1", report_id="r1", model_version="v1", cohort="NIFTY:60minute",
            train_window_json="{}", validation_window_json="{}", sample_count=100,
            metrics_json="{}", artifact_hash="abc", promotion_state="pending",
            created_at_ms=1000,
        ))
        repo.insert_calibration_state(dict(
            user_id="user-1", report_id="r2", model_version="v1", cohort="NIFTY:60minute",
            train_window_json="{}", validation_window_json="{}", sample_count=200,
            metrics_json="{}", artifact_hash="def", promotion_state="pending",
            created_at_ms=2000,
        ))
        latest = repo.fetch_latest_calibration_state("user-1")
        assert latest["report_id"] == "r2"


class TestFailsClosedWhenUnavailable:
    def test_all_writers_raise_when_store_unavailable(self, monkeypatch):
        monkeypatch.setattr(db, "_available", False)
        with pytest.raises(NavigatorStorageError):
            repo.insert_option_snapshot(_snapshot())
        with pytest.raises(NavigatorStorageError):
            repo.insert_feature_snapshot(_feature_snapshot())
        with pytest.raises(NavigatorStorageError):
            repo.insert_signal_event(_signal_event())
