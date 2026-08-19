from datetime import datetime, timedelta, timezone

from app.engines.nifty_orb_options import Bar, StrategyConfig, generate_signal, opening_range


def test_opening_range_uses_ist_when_bar_timestamps_are_utc():
    # 09:15 IST == 03:45 UTC.
    bars = [
        Bar(datetime(2026, 8, 19, 3, 45, tzinfo=timezone.utc), 100, 101, 99, 100.5, 1000),
        Bar(datetime(2026, 8, 19, 3, 50, tzinfo=timezone.utc), 100.5, 102, 100, 101.5, 1000),
        Bar(datetime(2026, 8, 19, 3, 55, tzinfo=timezone.utc), 101.5, 103, 101, 102.5, 1000),
        Bar(datetime(2026, 8, 19, 4, 0, tzinfo=timezone.utc), 102.5, 104, 102, 103.5, 1000),
    ]
    high, low = opening_range(bars, 15)
    assert high == 103
    assert low == 99


def test_realtime_signal_ignores_forming_bar():
    ist = timezone(timedelta(hours=5, minutes=30))
    bars = [
        Bar(datetime(2026, 8, 19, 9, 15, tzinfo=ist), 100, 101, 99, 100, 1000),
        Bar(datetime(2026, 8, 19, 9, 20, tzinfo=ist), 100, 102, 99, 101, 1000),
        Bar(datetime(2026, 8, 19, 9, 25, tzinfo=ist), 101, 103, 100, 102, 1000),
        Bar(datetime(2026, 8, 19, 9, 30, tzinfo=ist), 102, 110, 101, 109, 5000),
    ]
    cfg = StrategyConfig(min_breakout_atr=0.01, volume_multiplier=1.0)
    as_of = datetime(2026, 8, 19, 9, 32, tzinfo=ist)
    signal = generate_signal(bars, cfg, as_of=as_of)
    assert signal.timestamp == datetime(2026, 8, 19, 9, 25, tzinfo=ist)
