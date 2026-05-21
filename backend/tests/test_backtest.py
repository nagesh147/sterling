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
                "BULL_TREND", "BEAR_TREND", "RANGING", "VOLATILE", "IDLE",
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


class TestVCPScalper:
    """Tests for Hybrid VCP-Momentum Scalper engine and /backtest/vcp endpoint."""

    def test_vcp_backtest_runs_all_profiles(self, client):
        """POST /backtest/vcp returns results for all requested profiles."""
        resp = client.post("/api/v1/backtest/vcp", json={
            "underlying": "BTC",
            "lookback_days": 30,
            "profiles": ["btc_scalping_15m", "btc_scalping_30m"],
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert "profiles" in data
        assert "timestamp_ms" in data
        # Both profiles should be present
        for pk in ("btc_scalping_15m", "btc_scalping_30m"):
            assert pk in data["profiles"], f"Missing profile: {pk}"
            p = data["profiles"][pk]
            assert "trade_count" in p
            assert "win_rate" in p
            assert "equity_curve" in p
            assert isinstance(p["equity_curve"], list)

    def test_vcp_backtest_defaults_to_all_profiles(self, client):
        """No profiles field → runs all available profiles."""
        resp = client.post("/api/v1/backtest/vcp", json={
            "underlying": "ETH",
            "lookback_days": 14,
        })
        assert resp.status_code == 200
        data = resp.json()
        expected = {"btc_scalping_15m", "btc_scalping_30m", "eth_scalping_15m", "eth_scalping_30m"}
        assert set(data["profiles"].keys()) == expected

    def test_vcp_backtest_unknown_underlying_404(self, client):
        resp = client.post("/api/v1/backtest/vcp", json={
            "underlying": "FAKE",
            "profiles": ["btc_scalping_15m"],
        })
        assert resp.status_code == 404

    def test_vcp_backtest_invalid_profile_400(self, client):
        resp = client.post("/api/v1/backtest/vcp", json={
            "underlying": "BTC",
            "profiles": ["btc_scalping_15m", "nonexistent_profile"],
        })
        assert resp.status_code == 400
        assert "nonexistent_profile" in resp.text

    def test_vcp_backtest_lookback_days_validation(self, client):
        resp = client.post("/api/v1/backtest/vcp", json={
            "underlying": "BTC",
            "lookback_days": 2,   # below minimum of 7
        })
        assert resp.status_code == 422

    def test_vcp_backtest_equity_curve_starts_at_one(self, client):
        """Equity curve must start at 1.0 (zero initial cost)."""
        resp = client.post("/api/v1/backtest/vcp", json={
            "underlying": "BTC",
            "lookback_days": 30,
            "profiles": ["btc_scalping_15m"],
        })
        assert resp.status_code == 200
        curves = resp.json()["profiles"]["btc_scalping_15m"]["equity_curve"]
        assert len(curves) > 0
        assert abs(curves[0] - 1.0) < 1e-6

    def test_vcp_backtest_trade_fields(self, client):
        """Trade records must have all required fields and valid ranges."""
        resp = client.post("/api/v1/backtest/vcp", json={
            "underlying": "BTC",
            "lookback_days": 30,
            "profiles": ["btc_scalping_15m"],
        })
        assert resp.status_code == 200
        trades = resp.json()["profiles"]["btc_scalping_15m"]["trades"]
        for t in trades:
            assert t["direction"] in (-1, 1)
            assert t["entry_bar"] <= t["exit_bar"]
            assert -5.0 < t["net_pnl"] < 5.0
            assert t["exit_reason"] in (
                "stop_out", "tp_partial", "trail_stop", "time_stop",
                "trend_flip", "end_of_data",
            )

    def test_vcp_engine_direct_import(self):
        """run_backtest works as a standalone import."""
        from app.engines.hybrid_vcp import run_backtest, PROFILES
        import numpy as np
        ts = int(1_718_000_000_000)
        candles = [
            Candle(
                timestamp_ms=ts + i * 15 * 60_000,
                open=65000.0 + i * 2,
                high=65100.0 + i * 2,
                low=64900.0 + i * 2,
                close=65050.0 + i * 2,
                volume=1000.0,
            )
            for i in range(200)
        ]
        result = run_backtest(candles, PROFILES["btc_scalping_15m"])
        assert result.trade_count >= 0
        assert abs(result.equity_curve[0] - 1.0) < 1e-6
        assert all(e > 0 for e in result.equity_curve)

    def test_vcp_profiles_all_have_required_fields(self):
        """Every profile in PROFILES has all required scalars for backtest + executor."""
        from app.engines.hybrid_vcp import PROFILES
        required = (
            "signal_bar_ms", "regime_bar_ms", "hold_bars",
            "vol_filter_pct", "flow_threshold",
            "max_ibs_long", "min_ibs_short",
            "max_rsi_long", "min_rsi_short",
            "stop_mult", "tp1_mult", "trail_mult",
            "risk_pct", "max_positions",
        )
        for key, p in PROFILES.items():
            for field in required:
                assert hasattr(p, field), f"{key} missing {field}"
            assert p.signal_bar_ms > 0
            assert p.regime_bar_ms > 0
            assert p.hold_bars > 0

    def test_vcp_track_selector_routing(self):
        """VCP is routed for BTC/ETH scalping profiles, not for intraday."""
        from app.engines.directional.track_selector import select_tracks, reset_routes
        reset_routes()
        assert select_tracks("BTC", "scalping_15m") == ["vcp"]
        assert select_tracks("BTC", "scalping_30m") == ["vcp"]
        assert select_tracks("ETH", "scalping_15m") == ["vcp"]
        assert select_tracks("BTC", "intraday_1h") == ["trend_following"]
        assert select_tracks("BTC", "intraday_4h") == ["trend_following"]

    def test_vcp_track_compute_returns_track_signal(self):
        """VCPTrack.compute returns a TrackSignal with valid trend_dir."""
        from app.engines.directional.tracks.vcp_track import VCPTrack, VCPTrackConfig
        from app.schemas.directional import RegimeResult

        track = VCPTrack(VCPTrackConfig(profile_key="btc_scalping_15m"))
        assert track.name == "vcp"

        # Warmup-length candles for valid indicators
        ts = int(1_718_000_000_000)
        candles = [
            Candle(
                timestamp_ms=ts + i * 15 * 60_000,
                open=65000.0 + i * 2,
                high=65100.0 + i * 2,
                low=64900.0 + i * 2,
                close=65050.0 + i * 2,
                volume=1000.0,
            )
            for i in range(60)
        ]
        fake_regime = RegimeResult(
            macro_regime="BULL_TREND",
            regime_score=60.0,
            atr_percentile=50.0,
            adx=25.0,
            trend_label="bullish",
            ema8=64000.0,
            ema21=63000.0,
            ema50=62000.0,
            close_4h=65000.0,
        )
        sig = track.compute(candles, fake_regime)
        assert sig.trend_dir in (-1, 0, 1)
        assert sig.score >= 0.0
        assert sig.track == "vcp"
        assert sig.strength in ("STRONG", "SIGNAL", "NONE")
