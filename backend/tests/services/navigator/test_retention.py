"""Phase 7 test: bounded retention (spec §14.7)."""
from __future__ import annotations

import os
import tempfile

import pytest

from app.services import db
from app.services.navigator import repository as repo


@pytest.fixture(autouse=True)
def isolated_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    yield
    os.unlink(path)


def _snapshot(sample_bucket_ms, token=1):
    return dict(
        account_scope="acct-1", underlying="NIFTY 50", spot_token=1, spot=100.0, exchange="NFO",
        expiry="2026-08-06", instrument_token=token, tradingsymbol=f"X{token}", option_type="CE",
        strike=100.0, lot_size=75, tick_size=0.05, bid=1.0, ask=1.1, last_price=1.05, mid=1.05,
        implied_volatility=0.2, open_interest=10, cumulative_volume=100,
        exchange_timestamp_ms=sample_bucket_ms, received_at_ms=sample_bucket_ms,
        sample_bucket_ms=sample_bucket_ms, quote_quality="ok", config_revision=1,
    )


def _feature(bar_close_ms):
    return dict(
        user_id="user-1", underlying="NIFTY 50", timeframe="60minute", bar_close_ms=bar_close_ms,
        observed_at_ms=bar_close_ms, config_revision=1, model_versions_json="{}", quality="ok",
        avwap_json=None, range_json=None, volatility_json=None, flow_json=None, gamma_json=None,
        input_hash=f"hash-{bar_close_ms}",
    )


class TestRunRetention:
    def test_deletes_only_option_snapshots_older_than_raw_days(self):
        now_ms = 100 * 86_400_000  # day 100
        old_ms = 1 * 86_400_000    # day 1 — far older than 30-day retention
        recent_ms = 99 * 86_400_000
        repo.insert_option_snapshot(_snapshot(old_ms, token=1))
        repo.insert_option_snapshot(_snapshot(recent_ms, token=2))

        result = repo.run_retention(raw_days=30, feature_days=365, now_ms=now_ms)

        assert result.option_snapshots_deleted == 1
        remaining = repo.fetch_option_snapshots("acct-1", "NIFTY 50", "2026-08-06", since_bucket_ms=0)
        assert [r["sample_bucket_ms"] for r in remaining] == [recent_ms]

    def test_deletes_only_feature_snapshots_older_than_feature_days(self):
        now_ms = 400 * 86_400_000
        old_ms = 1 * 86_400_000
        recent_ms = 399 * 86_400_000
        repo.insert_feature_snapshot(_feature(old_ms))
        repo.insert_feature_snapshot(_feature(recent_ms))

        result = repo.run_retention(raw_days=30, feature_days=365, now_ms=now_ms)
        assert result.feature_snapshots_deleted == 1

    def test_reports_oldest_timestamps_and_db_bytes(self):
        now_ms = 100 * 86_400_000
        repo.insert_option_snapshot(_snapshot(50 * 86_400_000, token=1))
        repo.insert_feature_snapshot(_feature(50 * 86_400_000))
        result = repo.run_retention(raw_days=365, feature_days=3650, now_ms=now_ms)
        assert result.oldest_option_snapshot_ms == 50 * 86_400_000
        assert result.oldest_feature_snapshot_ms == 50 * 86_400_000
        assert result.database_bytes is not None and result.database_bytes > 0

    def test_deletes_in_bounded_batches(self):
        now_ms = 100 * 86_400_000
        old_ms = 1 * 86_400_000
        for i in range(12):
            repo.insert_option_snapshot(_snapshot(old_ms + i, token=i))  # 12 distinct old rows
        result = repo.run_retention(raw_days=30, feature_days=365, now_ms=now_ms, batch_size=5)
        assert result.option_snapshots_deleted == 12  # multiple batches still delete everything due

    def test_signal_events_and_config_are_never_touched_by_retention(self):
        # immutable signal events (and config/audit) are outside this
        # function's scope entirely — retention only targets raw/feature tables.
        repo.insert_signal_event(dict(
            decision_id="d1", user_id="user-1", underlying="NIFTY 50", bar_close_ms=1,
            generated_at_ms=1, direction="long", status="CONFIRMED", effective_score=80.0,
            execution_eligible=1, config_revision=1, payload_json="{}",
        ))
        repo.run_retention(raw_days=0, feature_days=0, now_ms=100 * 86_400_000)
        assert repo.fetch_signal_event("d1") is not None
