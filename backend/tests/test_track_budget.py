"""Tests for `engines/risk/track_budget.py` cross-track sizing rules."""
import pytest

from app.engines.risk import track_budget as tb


@pytest.fixture(autouse=True)
def _reset_budget():
    tb.reset()
    yield
    tb.reset()


def test_no_active_tracks_full_size():
    assert tb.size_multiplier("BTC", "scalping_30m", "mean_reversion") == 1.0


def test_one_other_track_open_gets_half_size():
    tb.record_open("BTC", "scalping_30m", "mean_reversion")
    assert tb.size_multiplier("BTC", "scalping_30m", "ml_ensemble") == 0.5
    # Same track re-firing on same instrument doesn't count as "other".
    assert tb.size_multiplier("BTC", "scalping_30m", "mean_reversion") == 1.0


def test_two_other_tracks_open_gets_quarter_size():
    tb.record_open("BTC", "scalping_30m", "mean_reversion")
    tb.record_open("BTC", "scalping_30m", "ml_ensemble")
    assert tb.size_multiplier("BTC", "scalping_30m", "trend_following") == 0.25


def test_close_releases_slot():
    tb.record_open("BTC", "scalping_30m", "mean_reversion")
    assert tb.size_multiplier("BTC", "scalping_30m", "ml_ensemble") == 0.5
    tb.record_close("BTC", "scalping_30m", "mean_reversion")
    assert tb.size_multiplier("BTC", "scalping_30m", "ml_ensemble") == 1.0


def test_isolated_per_instrument():
    tb.record_open("BTC", "scalping_30m", "mean_reversion")
    # ETH on the same profile is independent.
    assert tb.size_multiplier("ETH", "scalping_30m", "trend_following") == 1.0


def test_isolated_per_profile():
    tb.record_open("BTC", "scalping_30m", "mean_reversion")
    # Different profile on the same asset is independent.
    assert tb.size_multiplier("BTC", "scalping_15m", "trend_following") == 1.0


def test_close_idempotent():
    tb.record_close("BTC", "scalping_30m", "mean_reversion")  # no-op
    tb.record_open("BTC", "scalping_30m", "mean_reversion")
    tb.record_close("BTC", "scalping_30m", "mean_reversion")
    tb.record_close("BTC", "scalping_30m", "mean_reversion")  # no-op
    assert tb.size_multiplier("BTC", "scalping_30m", "ml_ensemble") == 1.0


def test_snapshot_shape():
    tb.record_open("BTC", "scalping_30m", "mean_reversion")
    tb.record_open("BTC", "scalping_30m", "ml_ensemble")
    tb.record_open("ETH", "intraday_1h", "trend_following")
    snap = tb.snapshot()
    assert "BTC/scalping_30m" in snap
    assert sorted(snap["BTC/scalping_30m"]) == ["mean_reversion", "ml_ensemble"]
    assert snap["ETH/intraday_1h"] == ["trend_following"]


def test_max_dampen_floor():
    """≥3 concurrent tracks all get the floor multiplier (0.125x), no negatives."""
    tb.record_open("BTC", "scalping_30m", "a")
    tb.record_open("BTC", "scalping_30m", "b")
    tb.record_open("BTC", "scalping_30m", "c")
    tb.record_open("BTC", "scalping_30m", "d")
    mult = tb.size_multiplier("BTC", "scalping_30m", "new_track")
    assert mult >= 0.125
    assert mult <= 0.25


def test_asset_normalisation_lookup():
    """Asset key normalisation matches what the router does."""
    tb.record_open("btc", "scalping_30m", "mean_reversion")
    # Stored as "BTC" → looking up "BTC" should find it.
    assert "mean_reversion" in tb.active_tracks("BTC", "scalping_30m")
