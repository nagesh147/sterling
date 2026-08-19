from datetime import datetime, timezone
from app.engines.nifty_orb_options import Bar, StrategyConfig, opening_range


def test_opening_range_uses_ist_when_bar_timestamps_are_utc():
    # 09:15 IST == 03:45 UTC.
    bars=[
        Bar(datetime(2026,8,19,3,45,tzinfo=timezone.utc),100,101,99,100.5,1000),
        Bar(datetime(2026,8,19,3,50,tzinfo=timezone.utc),100.5,102,100,101.5,1000),
        Bar(datetime(2026,8,19,3,55,tzinfo=timezone.utc),101.5,103,101,102.5,1000),
        Bar(datetime(2026,8,19,4,0,tzinfo=timezone.utc),102.5,104,102,103.5,1000),
    ]
    high,low=opening_range(bars,15)
    assert high==103
    assert low==99
