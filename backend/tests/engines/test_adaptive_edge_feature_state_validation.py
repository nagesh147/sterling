from datetime import datetime, timedelta

from app.engines.adaptive_edge.feature_state import MarketSnapshot, build_feature_state


def snap(t, **overrides):
    values = dict(
        instrument="NIFTY",
        timestamp=t,
        bid=100.0,
        ask=101.0,
        ltp=100.5,
        ttq=1000.0,
        bid_qty=50.0,
        ask_qty=30.0,
        trade_price=101.0,
        trade_volume=10.0,
    )
    values.update(overrides)
    return MarketSnapshot(**values)


def test_non_positive_prices_are_data_quality_failure():
    t = datetime(2026, 1, 1, 9, 15, tzinfo=None)
    assert not build_feature_state(snap(t, bid=0.0), None).data_ok
    assert not build_feature_state(snap(t, ltp=0.0), None).data_ok


def test_negative_trade_volume_is_data_quality_failure():
    t = datetime(2026, 1, 1, 9, 15)
    assert not build_feature_state(snap(t, trade_volume=-1.0), None).data_ok


def test_first_snapshot_does_not_invent_interval_trade_volume():
    t = datetime(2026, 1, 1, 9, 15)
    state = build_feature_state(snap(t), None)
    assert state.incremental_volume is None
    assert state.delta == 0.0
    assert state.unknown_volume == 0.0


def test_cross_instrument_state_is_rejected():
    t = datetime(2026, 1, 1, 9, 15)
    with __import__("pytest").raises(ValueError):
        build_feature_state(snap(t + timedelta(seconds=1), instrument="BANKNIFTY"), snap(t))
