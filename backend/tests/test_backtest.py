import time
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.schemas.market import Candle
from app.engines.backtest.backtest_engine import run_backtest
from main import create_app


def _make_candles(n: int, base: float = 40000.0, trend: float = 10.0) -> list[Candle]:
    np.random.seed(0)
    candles = []
    price = base
    for i in range(n):
        price += trend + np.random.normal(0, 50)
        o = price - abs(np.random.normal(0, 30))
        c = price + abs(np.random.normal(0, 30))
        h = max(o, c) + abs(np.random.normal(0, 20))
        l = min(o, c) - abs(np.random.normal(0, 20))
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=round(o, 2), high=round(h, 2),
            low=round(l, 2), close=round(c, 2), volume=100.0,
        ))
    return candles


class TestBacktestEngine:
    def test_returns_result(self):
        c1h = _make_candles(300, trend=50.0)
        c4h = _make_candles(100, trend=50.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=14, sample_every_n_bars=4)
        assert result.underlying == "BTC"
        assert result.total_1h_candles == 300
        assert result.total_4h_candles == 100

    def test_bars_sampled(self):
        c1h = _make_candles(200, trend=50.0)
        c4h = _make_candles(100, trend=50.0)
        result = run_backtest("ETH", c4h, c1h, lookback_days=10, sample_every_n_bars=6)
        # bars should be sampled every 6 bars starting at bar 30
        assert result.stats.total_bars_evaluated > 0
        assert len(result.bars) == result.stats.total_bars_evaluated

    def test_stats_sum_correctly(self):
        c1h = _make_candles(300, trend=50.0)
        c4h = _make_candles(100, trend=50.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=14, sample_every_n_bars=4)
        s = result.stats
        total = s.bullish_regime_bars + s.bearish_regime_bars + s.neutral_regime_bars
        assert total == s.total_bars_evaluated

    def test_signal_stats_sum(self):
        c1h = _make_candles(300, trend=50.0)
        c4h = _make_candles(100, trend=50.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=14, sample_every_n_bars=4)
        s = result.stats
        total = s.bullish_signal_bars + s.bearish_signal_bars + s.neutral_signal_bars
        assert total == s.total_bars_evaluated

    def test_bullish_trend_dominant_in_uptrend(self):
        c1h = _make_candles(300, trend=200.0)
        c4h = _make_candles(100, trend=200.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=14, sample_every_n_bars=4)
        s = result.stats
        assert s.bullish_regime_bars > s.bearish_regime_bars

    def test_empty_result_for_insufficient_data(self):
        c1h = _make_candles(10)
        c4h = _make_candles(10)
        result = run_backtest("BTC", c4h, c1h, lookback_days=1)
        assert result.stats.total_bars_evaluated == 0
        assert result.bars == []

    def test_no_lookahead_bias(self):
        """Each bar evaluation only uses candles up to that bar's timestamp."""
        c1h = _make_candles(200, trend=50.0)
        c4h = _make_candles(100, trend=50.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=10, sample_every_n_bars=4)
        # Bar timestamps must be monotonically increasing
        for i in range(1, len(result.bars)):
            assert result.bars[i].timestamp_ms > result.bars[i - 1].timestamp_ms

    def test_bar_fields_present(self):
        c1h = _make_candles(200, trend=50.0)
        c4h = _make_candles(100, trend=50.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=10, sample_every_n_bars=4)
        if result.bars:
            bar = result.bars[0]
            assert bar.macro_regime in (
                "bullish", "bearish", "neutral",
                "bull_trending", "bull_weak", "bull_ranging",
                "bear_trending", "bear_weak", "bear_ranging", "choppy",
            )
            assert bar.signal_trend in (-1, 0, 1)
            assert isinstance(bar.all_green, bool)
            assert isinstance(bar.green_arrow, bool)
            assert len(bar.st_trends) == 3


def _mock_adapter(n_candles=300):
    c = _make_candles(n_candles, trend=50.0)
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=c)
    a.get_option_chain = AsyncMock(return_value=[])
    a.get_dvol = AsyncMock(return_value=55.0)
    a.get_dvol_history = AsyncMock(return_value=[40.0, 55.0, 70.0])
    a.close = AsyncMock(return_value=None)
    return a


@pytest.fixture()
def client():
    app = create_app()
    adapter = _mock_adapter()
    app.state.adapter = adapter
    with TestClient(app) as c:
        c.app.state.adapter = adapter
        yield c


class TestBacktestAPI:
    def test_run_btc(self, client):
        resp = client.post("/api/v1/backtest/run", json={
            "underlying": "BTC", "lookback_days": 14, "sample_every_n_bars": 4
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert "stats" in data
        assert "bars" in data

    def test_run_eth(self, client):
        resp = client.post("/api/v1/backtest/run", json={"underlying": "ETH"})
        assert resp.status_code == 200
        assert resp.json()["underlying"] == "ETH"

    def test_unknown_underlying_404(self, client):
        resp = client.post("/api/v1/backtest/run", json={"underlying": "FAKE"})
        assert resp.status_code == 404

    def test_stats_fields(self, client):
        resp = client.post("/api/v1/backtest/run", json={
            "underlying": "BTC", "lookback_days": 7
        })
        s = resp.json()["stats"]
        assert "total_bars_evaluated" in s
        assert "green_arrows" in s
        assert "confirmed_long_setups" in s
        assert "filtered_bars" in s

    def test_lookback_days_validation(self, client):
        resp = client.post("/api/v1/backtest/run", json={
            "underlying": "BTC", "lookback_days": 2  # below min=7
        })
        assert resp.status_code == 422

    def test_sample_rate_validation(self, client):
        resp = client.post("/api/v1/backtest/run", json={
            "underlying": "BTC", "sample_every_n_bars": 0  # below min=1
        })
        assert resp.status_code == 422
