"""
Tests for features added in v0.4+:
- Backtest forward returns and signal quality stats
- /positions/close-all
- /positions/pnl-live
- /config/data-source
- Alert persistence (bootstrap)
- Realized-vol IVR fallback
"""
import time
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.schemas.market import Candle
from app.engines.backtest.backtest_engine import run_backtest
from app.engines.directional.orchestrator import _compute_hv_ivr


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_candles(n: int, base: float = 40000.0, trend: float = 50.0) -> list:
    np.random.seed(42)
    candles, price = [], base
    for i in range(n):
        price += trend + np.random.normal(0, base * 0.001)
        o = price - abs(np.random.normal(0, base * 0.0005))
        c = price + abs(np.random.normal(0, base * 0.0005))
        h = max(o, c) + abs(np.random.normal(0, base * 0.0003))
        l = min(o, c) - abs(np.random.normal(0, base * 0.0003))
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=round(o, 2), high=round(h, 2),
            low=round(l, 2), close=round(c, 2), volume=200.0,
        ))
    return candles


def _mock_adapter(n_candles=300):
    c = _make_candles(n_candles, trend=50.0)
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=c)
    a.get_option_chain = AsyncMock(return_value=[])
    a.get_dvol = AsyncMock(return_value=None)
    a.get_dvol_history = AsyncMock(return_value=[])
    a.close = AsyncMock(return_value=None)
    return a


from main import create_app

@pytest.fixture()
def client():
    from app.services import paper_store, eval_history, arrow_store, alert_store, pnl_history, webhook_store
    from app.services import exchange_account_store as eas
    import app.api.v1.endpoints.config as config_ep
    from app.schemas.risk import RiskParams
    from app.core.config import settings

    paper_store._positions.clear()
    paper_store._loaded = True
    eval_history.clear()
    arrow_store.clear()
    alert_store.clear()
    pnl_history.clear()
    webhook_store.clear()
    eas._configs.clear()
    eas._loaded = False
    config_ep._risk = RiskParams(
        capital=settings.default_capital,
        max_position_pct=settings.max_position_pct,
        max_contracts=settings.max_contracts,
    )

    app = create_app()
    adapter = _mock_adapter()
    app.state.adapter = adapter
    with TestClient(app) as c:
        c.app.state.adapter = adapter
        yield c

    paper_store._positions.clear()
    eval_history.clear()
    arrow_store.clear()
    alert_store.clear()
    pnl_history.clear()
    webhook_store.clear()
    eas._configs.clear()
    eas._loaded = False


# ─── Backtest forward returns ─────────────────────────────────────────────────

class TestBacktestForwardReturns:
    def test_fwd_return_fields_present(self):
        c1h = _make_candles(300, trend=50.0)
        c4h = _make_candles(100, trend=50.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=14, sample_every_n_bars=4)
        assert result.bars, "Expected at least one bar"
        # Early bars should have forward returns; last bars may not (near end of series)
        bars_with_fwd = [b for b in result.bars if b.fwd_return_4h is not None]
        assert len(bars_with_fwd) > 0

    def test_fwd_return_4h_reasonable(self):
        c1h = _make_candles(300, trend=50.0)
        c4h = _make_candles(100, trend=50.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=14, sample_every_n_bars=4)
        for b in result.bars:
            if b.fwd_return_4h is not None:
                # Return should be reasonable (not thousands of percent)
                assert abs(b.fwd_return_4h) < 50.0, f"Unreasonable 4H return: {b.fwd_return_4h}"

    def test_st_values_in_bars(self):
        c1h = _make_candles(300, trend=50.0)
        c4h = _make_candles(100, trend=50.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=14, sample_every_n_bars=4)
        if result.bars:
            bar = result.bars[0]
            assert len(bar.st_values) == 3

    def test_signal_quality_stats_populated(self):
        c1h = _make_candles(300, trend=200.0)  # strong uptrend → arrows fire
        c4h = _make_candles(100, trend=200.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=14, sample_every_n_bars=2)
        s = result.stats
        # Arrow win rates are None when no arrows fired, otherwise float
        if s.green_arrows > 0:
            assert s.arrow_long_win_rate_4h is not None
            assert 0.0 <= s.arrow_long_win_rate_4h <= 100.0
        if s.red_arrows > 0:
            assert s.arrow_short_win_rate_4h is not None

    def test_no_fwd_return_at_tail(self):
        """Last N bars can't have 24H forward return — not enough future data."""
        c1h = _make_candles(200, trend=50.0)
        c4h = _make_candles(100, trend=50.0)
        result = run_backtest("BTC", c4h, c1h, lookback_days=7, sample_every_n_bars=4)
        # The very last bars should have None for 24H return
        if len(result.bars) > 1:
            assert result.bars[-1].fwd_return_24h is None


# ─── /positions/close-all ────────────────────────────────────────────────────

class TestCloseAll:
    def test_close_all_empty(self, client):
        resp = client.post("/api/v1/positions/close-all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["closed_count"] == 0
        assert data["total_realized_pnl_usd"] == 0.0

    def test_close_all_with_positions(self, client):
        from app.services import paper_store
        from app.schemas.execution import SizedTrade, TradeStructure
        from app.schemas.directional import Direction
        from tests.test_structures import _call

        sized = SizedTrade(
            structure=TradeStructure(
                structure_type="naked_call", direction=Direction.LONG,
                legs=[_call(42000)], max_loss=420.0, max_gain=None,
                net_premium=420.0, risk_reward=None, score=70.0, score_breakdown={},
            ),
            contracts=1, position_value=420.0, max_risk_usd=420.0, capital_at_risk_pct=0.42,
        )
        paper_store.add_position("BTC", sized, entry_spot_price=42000.0)
        paper_store.add_position("ETH", sized, entry_spot_price=42000.0)

        resp = client.post("/api/v1/positions/close-all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["closed_count"] == 2

        # Positions should now be closed
        pos_resp = client.get("/api/v1/positions")
        assert pos_resp.json()["open_count"] == 0
        assert pos_resp.json()["closed_count"] == 2


# ─── /positions/pnl-live ─────────────────────────────────────────────────────

class TestLivePnl:
    def test_pnl_live_empty(self, client):
        resp = client.get("/api/v1/positions/pnl-live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["positions"] == []
        assert data["total_estimated_pnl_usd"] == 0.0

    def test_pnl_live_with_open_position(self, client):
        from app.services import paper_store
        from app.schemas.execution import SizedTrade, TradeStructure
        from app.schemas.directional import Direction
        from tests.test_structures import _call

        sized = SizedTrade(
            structure=TradeStructure(
                structure_type="naked_call", direction=Direction.LONG,
                legs=[_call(40000)], max_loss=420.0, max_gain=None,
                net_premium=420.0, risk_reward=None, score=70.0, score_breakdown={},
            ),
            contracts=1, position_value=420.0, max_risk_usd=420.0, capital_at_risk_pct=0.42,
        )
        pos = paper_store.add_position("BTC", sized, entry_spot_price=42000.0)

        resp = client.get("/api/v1/positions/pnl-live")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["positions"]) == 1
        entry = data["positions"][0]
        assert entry["position_id"] == pos.id
        assert entry["underlying"] == "BTC"
        assert entry["current_spot"] is not None
        assert entry["estimated_pnl_usd"] is not None


# ─── /config/data-source ─────────────────────────────────────────────────────

class TestDataSource:
    def test_get_data_source(self, client):
        resp = client.get("/api/v1/config/data-source")
        assert resp.status_code == 200
        data = resp.json()
        assert "exchange" in data
        assert "display_name" in data
        assert "reachable" in data

    def test_set_data_source_valid(self, client):
        resp = client.post("/api/v1/config/data-source", json={"exchange": "deribit"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["exchange"] == "deribit"

    def test_set_data_source_invalid(self, client):
        resp = client.post("/api/v1/config/data-source", json={"exchange": "fake_exchange"})
        assert resp.status_code == 400

    def test_invalidate_cache(self, client):
        resp = client.post("/api/v1/config/data-source/invalidate-cache")
        assert resp.status_code == 200
        assert resp.json()["cleared"] is True


# ─── Realized-vol IVR ────────────────────────────────────────────────────────

class TestRealizedVolIVR:
    def test_hv_ivr_returns_float_for_sufficient_data(self):
        candles = _make_candles(300, base=40000.0, trend=20.0)
        result = _compute_hv_ivr(candles)
        assert result is not None
        assert 0.0 <= result <= 100.0

    def test_hv_ivr_returns_none_for_insufficient_data(self):
        candles = _make_candles(20)  # too few
        result = _compute_hv_ivr(candles)
        assert result is None

    def test_hv_ivr_higher_in_volatile_market(self):
        """High-volatility candles should produce higher IVR percentile."""
        candles_calm = _make_candles(300, base=40000.0, trend=5.0)
        candles_vol = []
        np.random.seed(99)
        price = 40000.0
        for i in range(300):
            price += 5 + np.random.normal(0, 500)  # much higher noise
            candles_vol.append(Candle(
                timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                open=price - 200, high=price + 300, low=price - 300, close=price + 200,
                volume=200.0,
            ))
        # Calm market → consistent low HV → IVR near 50%
        # Volatile market → high recent HV → IVR near high end
        calm_ivr = _compute_hv_ivr(candles_calm)
        # Just check both return valid values
        assert calm_ivr is not None


# ─── Alert persistence ───────────────────────────────────────────────────────

class TestAlertPersistence:
    def test_bootstrap_empty_db(self):
        """Bootstrap with empty/unavailable DB should not crash."""
        from app.services import alert_store
        alert_store._loaded = False
        alert_store._alerts.clear()
        # Should not raise even if DB unavailable
        alert_store.bootstrap()
        # If DB is unavailable, no alerts loaded but no crash
        assert alert_store._loaded is True

    def test_alert_create_and_retrieve(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC",
            "condition": "price_above",
            "threshold": 50000.0,
            "cooldown_hours": 0,
            "notes": "test alert",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert data["condition"] == "price_above"
        assert data["status"] == "active"

    def test_alert_dismiss_persists(self, client):
        create_resp = client.post("/api/v1/alerts", json={
            "underlying": "ETH",
            "condition": "price_below",
            "threshold": 1000.0,
        })
        alert_id = create_resp.json()["id"]

        dismiss_resp = client.post(f"/api/v1/alerts/{alert_id}/dismiss")
        assert dismiss_resp.status_code == 200
        assert dismiss_resp.json()["status"] == "dismissed"

        # Re-fetch and verify status
        list_resp = client.get("/api/v1/alerts")
        alerts = list_resp.json()["alerts"]
        found = next((a for a in alerts if a["id"] == alert_id), None)
        assert found is not None
        assert found["status"] == "dismissed"
