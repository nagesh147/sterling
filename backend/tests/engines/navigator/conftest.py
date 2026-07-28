import numpy as np
import pytest

from app.schemas.market import Candle

START_TS_MS = 1_753_000_000_000
STEP_MS = 3_600_000  # 1H bars, matches BASE_TIMEFRAME_MS


def make_candles(opens, highs, lows, closes, volumes, start_ts_ms=START_TS_MS, step_ms=STEP_MS):
    return [
        Candle(timestamp_ms=start_ts_ms + i * step_ms, open=float(o), high=float(h), low=float(l), close=float(c), volume=float(v))
        for i, (o, h, l, c, v) in enumerate(zip(opens, highs, lows, closes, volumes))
    ]


def random_walk_candles(n, seed=1, start=100.0, vol_mean=1000.0, start_ts_ms=START_TS_MS, step_ms=STEP_MS):
    rng = np.random.default_rng(seed)
    close = start + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close - rng.normal(0, 0.2, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0.3, 0.1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.3, 0.1, n))
    volume = np.abs(rng.normal(vol_mean, vol_mean * 0.1, n)) + 1.0
    return make_candles(open_, high, low, close, volume, start_ts_ms, step_ms)


def multi_session_candles(sessions, bars_per_session=6, seed=2, start=100.0, overnight_gap_ms=18 * 3_600_000):
    """`sessions` contiguous IST trading days, `bars_per_session` 1H bars each,
    with an overnight gap between sessions so `ist_calendar_dates` groups
    them into distinct days."""
    rng = np.random.default_rng(seed)
    candles = []
    ts = START_TS_MS
    price = start
    for _ in range(sessions):
        for _ in range(bars_per_session):
            o = price
            c = o + rng.normal(0, 0.3)
            h = max(o, c) + abs(rng.normal(0.2, 0.05))
            l = min(o, c) - abs(rng.normal(0.2, 0.05))
            v = abs(rng.normal(1000, 50)) + 1.0
            candles.append(Candle(timestamp_ms=ts, open=o, high=h, low=l, close=c, volume=v))
            price = c
            ts += STEP_MS
        ts += overnight_gap_ms
    return candles


@pytest.fixture
def warm_random_walk():
    return random_walk_candles(250, seed=11)
