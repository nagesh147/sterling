from datetime import datetime, timedelta
import pytest

from app.engines.adaptive_edge.feature_state import MarketSnapshot, build_feature_state


def snap(t, *, bid=100.0, ask=101.0, ltp=100.5, ttq=1000.0, trade_price=101.0, trade_volume=10.0, bid_qty=50.0, ask_qty=30.0):
    return MarketSnapshot("NIFTY", t, bid, ask, ltp, ttq, bid_qty, ask_qty, trade_price, trade_volume)


def test_feature_state_uses_causal_previous_snapshot():
    t0 = datetime(2026, 1, 1, 9, 15)
    state = build_feature_state(snap(t0 + timedelta(seconds=1), ttq=1010), snap(t0, ttq=1000))
    assert state.price_change == 0.0
    assert state.incremental_volume == 10
    assert state.aggressive_buy_volume == 10
    assert state.liquidity_imbalance == 0.25


def test_negative_cumulative_volume_is_data_error():
    t0 = datetime(2026, 1, 1, 9, 15)
    state = build_feature_state(snap(t0 + timedelta(seconds=1), ttq=900), snap(t0, ttq=1000))
    assert state.incremental_volume is None
    assert not state.data_ok


def test_snapshots_must_be_strictly_chronological():
    t0 = datetime(2026, 1, 1, 9, 15)
    with pytest.raises(ValueError):
        build_feature_state(snap(t0), snap(t0))
