from datetime import datetime, timedelta, timezone

from app.engines.nifty_orb_options import Bar, StrategyConfig, generate_signal

IST = timezone(timedelta(hours=5, minutes=30))


def _bars(closes: list[float], volumes: list[float]) -> list[Bar]:
    out = []
    for i, close in enumerate(closes):
        ts = datetime(2026, 8, 19, 9, 15, tzinfo=IST) + timedelta(minutes=5 * i)
        out.append(Bar(ts, close - 1, close + 1, close - 1, close, volumes[i]))
    return out


def test_vwap_slope_is_required_for_long_signal():
    cfg = StrategyConfig(min_breakout_atr=0.01, volume_multiplier=1.0, vwap_slope_lookback=2)
    # Opening range 09:15-09:30, then a breakout whose price is above VWAP.
    bars = _bars([100, 100, 101, 102, 103, 105], [100, 100, 100, 100, 100, 500])
    signal = generate_signal(bars, cfg)
    assert signal.direction == "LONG"


def test_flat_vwap_does_not_confirm_direction():
    cfg = StrategyConfig(min_breakout_atr=0.01, volume_multiplier=1.0, vwap_slope_lookback=2)
    bars = _bars([100, 100, 100, 100, 100, 105], [100, 100, 100, 100, 100, 500])
    signal = generate_signal(bars, cfg)
    assert signal.direction == "NONE"
