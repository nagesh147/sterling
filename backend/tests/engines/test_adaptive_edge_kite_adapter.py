from app.engines.adaptive_edge.kite_adapter import build_replay_bars
from app.schemas.market import Candle


def candles(n=40):
    return [
        Candle(
            timestamp_ms=i * 60_000,
            open=100.0 + i * 0.2,
            high=101.0 + i * 0.2,
            low=99.0 + i * 0.2,
            close=100.5 + i * 0.2,
            volume=1000.0 + (i % 5) * 100,
        )
        for i in range(n)
    ]


def test_adapter_is_deterministic_and_causal():
    a = build_replay_bars(candles())
    b = build_replay_bars(candles())
    assert a == b
    assert len(a) == 40
    assert all(-1.0 <= x.features.trend <= 1.0 for x in a)
    assert all(-1.0 <= x.features.momentum <= 1.0 for x in a)


def test_future_candle_cannot_change_prior_feature():
    base = candles()
    before = build_replay_bars(base[:25])[24]
    after = build_replay_bars(base[:25] + [Candle(
        timestamp_ms=10_000_000,
        open=1000.0,
        high=1200.0,
        low=900.0,
        close=1100.0,
        volume=9_999_999.0,
    )])[24]
    assert before == after
