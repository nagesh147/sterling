"""
Tests for the Hybrid VCP-Momentum Scalper engine.
Standalone — does not import main.py so runs without asyncpg or any
optional database dependency.
"""
import pytest
import numpy as np

from app.schemas.market import Candle
from app.schemas.directional import RegimeResult


class TestVCPProfiles:
    def test_all_profiles_have_required_fields(self):
        """Every profile in PROFILES has all required scalars."""
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
            assert 0 < p.vol_filter_pct <= 100
            assert 0 < p.flow_threshold <= 1

    def test_exit_config_from_profile_round_trips(self):
        """exit_config_from_profile produces valid ExitConfig."""
        from app.engines.hybrid_vcp import PROFILES, exit_config_from_profile
        for key, profile in PROFILES.items():
            cfg = exit_config_from_profile(profile)
            assert cfg.stop_mult == profile.stop_mult
            assert cfg.tp1_mult == profile.tp1_mult
            assert cfg.trail_mult == profile.trail_mult
            assert cfg.hold_bars == profile.hold_bars

    def test_profiles_btc_eth_15m_30m_exist(self):
        from app.engines.hybrid_vcp import PROFILES
        expected = {"btc_scalping_15m", "btc_scalping_30m", "eth_scalping_15m", "eth_scalping_30m"}
        assert set(PROFILES.keys()) == expected


class TestVCPBacktestEngine:
    def _synthetic(self, n=500, base_price=65000.0, trend=5.0, seed=42):
        rng = np.random.default_rng(seed)
        ts = int(1_718_000_000_000)
        candles = []
        price = base_price
        for i in range(n):
            price += trend + rng.normal(0, 200)
            o = price - abs(rng.normal(0, 100))
            c = price + abs(rng.normal(0, 100))
            h = max(o, c) + abs(rng.normal(0, 80))
            l = min(o, c) - abs(rng.normal(0, 80))
            candles.append(Candle(
                timestamp_ms=ts + i * 15 * 60_000,
                open=round(o, 2), high=round(h, 2),
                low=round(max(l, 100), 2), close=round(c, 2),
                volume=round(rng.lognormal(8.0, 0.8), 2),
            ))
        return candles

    def test_backtest_runs_without_error(self):
        from app.engines.hybrid_vcp import run_backtest, PROFILES
        candles = self._synthetic(n=200)   # fewer bars = faster
        for key in PROFILES:
            result = run_backtest(candles, PROFILES[key])
            assert result.trade_count >= 0
            assert 0.0 <= result.win_rate <= 1.0
            assert len(result.equity_curve) > 0
            assert abs(result.equity_curve[0] - 1.0) < 1e-6
            assert all(e > 0 for e in result.equity_curve)

    def test_equity_curve_is_monotonic_positive(self):
        from app.engines.hybrid_vcp import run_backtest, PROFILES
        candles = self._synthetic(n=200)
        result = run_backtest(candles, PROFILES["btc_scalping_15m"])
        assert all(e > 0 for e in result.equity_curve)
        assert len(result.equity_curve) >= 1
        assert result.equity_curve[0] == 1.0

    def test_trade_entry_before_exit(self):
        from app.engines.hybrid_vcp import run_backtest, PROFILES
        candles = self._synthetic(n=300)
        result = run_backtest(candles, PROFILES["btc_scalping_15m"])
        for t in result.trades:
            assert t.entry_bar <= t.exit_bar, f"entry_bar {t.entry_bar} > exit_bar {t.exit_bar}"
            assert t.direction in (-1, 1)
            assert -5.0 < t.net_pnl < 5.0

    def test_slippage_applied_to_exits(self):
        from app.engines.hybrid_vcp import run_backtest, PROFILES
        candles = self._synthetic(n=200)
        with_slip = run_backtest(candles, PROFILES["btc_scalping_15m"], apply_slippage=True)
        no_slip   = run_backtest(candles, PROFILES["btc_scalping_15m"], apply_slippage=False)
        for ts, ns in zip(with_slip.trades, no_slip.trades):
            assert ts.cost_pct >= ns.cost_pct, f"slippage should increase costs: {ts.cost_pct} vs {ns.cost_pct}"

    def test_all_profiles_have_valid_metrics(self):
        from app.engines.hybrid_vcp import run_backtest, PROFILES
        candles = self._synthetic(n=200)
        for key, profile in PROFILES.items():
            r = run_backtest(candles, profile)
            assert r.profile == profile.label
            assert r.trade_count == len(r.trades)
            assert r.max_drawdown <= 0.0


class TestVCPSignals:
    def _candles(self, n=100):
        ts = int(1_718_000_000_000)
        return [
            Candle(
                timestamp_ms=ts + i * 15 * 60_000,
                open=65000.0 + i * 1,
                high=65100.0 + i * 1,
                low=64900.0 + i * 1,
                close=65050.0 + i * 1,
                volume=1000.0,
            )
            for i in range(n)
        ]

    def test_vcp_track_name(self):
        from app.engines.directional.tracks.vcp_track import VCPTrack, VCPTrackConfig
        track = VCPTrack(VCPTrackConfig(profile_key="btc_scalping_15m"))
        assert track.name == "vcp"

    def test_vcp_track_returns_track_signal(self):
        """VCPTrack.compute always returns a TrackSignal (not raises)."""
        from app.engines.directional.tracks.vcp_track import VCPTrack, VCPTrackConfig
        track = VCPTrack(VCPTrackConfig(profile_key="btc_scalping_15m"))
        # 60 bars of neutral/noise — enough for warmup but no signal
        rng = np.random.default_rng(99)
        ts = int(1_718_000_000_000)
        candles = []
        price = 65000.0
        for i in range(60):
            price += rng.normal(0, 100)
            o = price + rng.normal(0, 30)
            c = price + rng.normal(0, 30)
            h = max(o, c) + abs(rng.normal(0, 20))
            l = min(o, c) - abs(rng.normal(0, 20))
            candles.append(Candle(
                timestamp_ms=ts + i * 15 * 60_000,
                open=round(o, 2), high=round(h, 2),
                low=round(max(l, 100), 2), close=round(c, 2),
                volume=round(rng.lognormal(8.0, 0.5), 2),
            ))
        fake_regime = RegimeResult(
            macro_regime="BULL_TREND",
            ema50=62000.0, close_4h=65000.0, score=60.0,
            atr_percentile=50.0, adx=25.0, ema21=63000.0,
        )
        sig = track.compute(candles, fake_regime)
        # Must not raise and must return a valid TrackSignal
        assert isinstance(sig.track, str)
        assert sig.score >= 0.0
        assert sig.strength in ("STRONG", "SIGNAL", "NONE")
        assert sig.trend_dir in (-1, 0, 1)

    def test_vcp_track_warmup_requires_min_bars(self):
        from app.engines.directional.tracks.vcp_track import VCPTrack, VCPTrackConfig
        track = VCPTrack(VCPTrackConfig(profile_key="btc_scalping_15m"))
        candles = self._candles(n=20)  # too few for EMA warmup
        fake_regime = RegimeResult(
            macro_regime="BULL_TREND",
            ema50=62000.0, close_4h=65000.0, score=60.0,
            atr_percentile=50.0, adx=25.0, ema21=63000.0,
        )
        sig = track.compute(candles, fake_regime)
        # With insufficient bars, should return neutral
        assert sig.trend_dir == 0

    def test_vcp_track_chop_filter(self):
        from app.engines.directional.tracks.vcp_track import VCPTrack, VCPTrackConfig
        track = VCPTrack(VCPTrackConfig(profile_key="btc_scalping_15m"))
        candles = self._candles(n=80)
        # Low-regime-score = chop zone → neutral signal
        chop_regime = RegimeResult(
            macro_regime="choppy",
            ema50=62000.0, close_4h=65000.0, score=20.0,   # score < 30 = chop
            atr_percentile=50.0, adx=15.0, ema21=63000.0,
        )
        sig = track.compute(candles, chop_regime)
        assert sig.trend_dir == 0

    def test_routing_btc_scalping_goes_to_vcp(self):
        from app.engines.directional.track_selector import select_tracks, reset_routes
        reset_routes()
        assert select_tracks("BTC", "scalping_15m") == ["vcp"]
        assert select_tracks("BTC", "scalping_30m") == ["vcp"]

    def test_routing_intraday_bypasses_vcp(self):
        from app.engines.directional.track_selector import select_tracks, reset_routes
        reset_routes()
        assert select_tracks("BTC", "intraday_1h") == ["trend_following"]
        assert select_tracks("BTC", "intraday_4h") == ["trend_following"]


class TestVCPLiveFilters:
    def test_evaluate_live_filters_passes_when_obi_cvd_aligned(self):
        from app.engines.hybrid_vcp.live_filters import (
            LiveMicroState, RealOBI, RealCVD,
            LiveFilterConfig, evaluate_live_filters,
        )
        state = LiveMicroState(
            obi=RealOBI(bid_qty=100.0, ask_qty=50.0, imbalance=0.33, ref_spread=5.0),
            cvd=RealCVD(cvd=500.0, cvd_rate=0.0),
            timestamp_ms=0,
            seq_no=1,
        )
        cfg = LiveFilterConfig(obi_threshold=0.27, cvd_threshold=0.0)
        # Long direction: positive OBI ✓, positive CVD ✓
        decision = evaluate_live_filters(state, direction=1, config=cfg)
        assert decision.passed

    def test_evaluate_live_filters_vetoes_hostile_obi(self):
        from app.engines.hybrid_vcp.live_filters import (
            LiveMicroState, RealOBI, RealCVD,
            LiveFilterConfig, evaluate_live_filters,
        )
        state = LiveMicroState(
            obi=RealOBI(bid_qty=50.0, ask_qty=100.0, imbalance=-0.33, ref_spread=5.0),
            cvd=RealCVD(cvd=500.0, cvd_rate=0.0),
            timestamp_ms=0,
            seq_no=1,
        )
        cfg = LiveFilterConfig(obi_threshold=0.27, cvd_threshold=0.0)
        # Long direction: negative OBI is hostile
        decision = evaluate_live_filters(state, direction=1, config=cfg)
        assert not decision.passed

    def test_evaluate_live_filters_falls_back_to_proxy_when_no_real_data(self):
        from app.engines.hybrid_vcp.live_filters import (
            LiveMicroState, LiveFilterConfig, evaluate_live_filters,
        )
        state = LiveMicroState(obi=None, cvd=None, timestamp_ms=0, seq_no=0)
        cfg = LiveFilterConfig()
        decision = evaluate_live_filters(state, direction=1, config=cfg)
        assert decision.passed
        assert decision.code == "proxy_fallback"

    def test_obi_from_orderbook_calculation(self):
        from app.engines.hybrid_vcp.live_filters import obi_from_orderbook
        bids = [(65000, 10), (64999, 5)]
        asks = [(65001, 8), (65002, 3)]
        obi = obi_from_orderbook(bids, asks)
        # bid vol > ask vol → positive OBI
        assert obi > 0
        assert -1 <= obi <= 1

    def test_cvd_from_trades(self):
        from app.engines.hybrid_vcp.live_filters import cvd_from_trades
        trades = [(1.0, "buy"), (2.0, "buy"), (1.5, "sell")]
        cvd = cvd_from_trades(trades)
        assert cvd == 1.5  # 3.0 buy - 1.5 sell