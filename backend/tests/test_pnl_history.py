"""
Tests: P&L history store, pnl-history endpoint, auto-alert from SSE.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle
from app.services import pnl_history
from main import create_app


def _make_candles(n=100, trend=10.0):
    return [Candle(timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                   open=40000.0 + i * trend, high=40050.0 + i * trend,
                   low=39950.0 + i * trend, close=40005.0 + i * trend, volume=100.0)
            for i in range(n)]


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=_make_candles())
    a.get_option_chain = AsyncMock(return_value=[])
    a.get_dvol = AsyncMock(return_value=None)
    a.get_dvol_history = AsyncMock(return_value=[])
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


# ─── P&L History Store ────────────────────────────────────────────────────────

class TestPnLHistoryStore:
    def test_record_and_retrieve(self):
        now_ms = int(time.time() * 1000)
        pnl_history.record("POS001", 42000.0, 250.0, 12, now_ms)
        snaps = pnl_history.get_history("POS001")
        assert len(snaps) == 1
        assert snaps[0].spot_price == 42000.0
        assert snaps[0].estimated_pnl == 250.0
        assert snaps[0].current_dte == 12

    def test_multiple_snapshots(self):
        now = int(time.time() * 1000)
        for i in range(5):
            pnl_history.record("POS002", 42000.0 + i * 100, float(i * 50), 12 - i, now + i * 1000)
        snaps = pnl_history.get_history("POS002")
        assert len(snaps) == 5

    def test_empty_for_unknown(self):
        assert pnl_history.get_history("UNKNOWN") == []

    def test_clear_specific(self):
        now = int(time.time() * 1000)
        pnl_history.record("POS_A", 42000.0, 100.0, 10, now)
        pnl_history.record("POS_B", 43000.0, 200.0, 8, now)
        pnl_history.clear("POS_A")
        assert pnl_history.get_history("POS_A") == []
        assert len(pnl_history.get_history("POS_B")) == 1

    def test_clear_all(self):
        now = int(time.time() * 1000)
        pnl_history.record("POS_X", 40000.0, 50.0, 5, now)
        pnl_history.clear()
        assert pnl_history.get_history("POS_X") == []


# ─── P&L History Endpoint ─────────────────────────────────────────────────────

class TestPnLHistoryAPI:
    def test_pnl_history_empty(self, client):
        resp = client.get("/api/v1/positions/TESTPOS/pnl-history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["position_id"] == "TESTPOS"
        assert data["snapshots"] == []
        assert data["count"] == 0

    def test_pnl_history_after_record(self, client):
        now = int(time.time() * 1000)
        pnl_history.record("MYPOS01", 42000.0, 300.0, 11, now)
        resp = client.get("/api/v1/positions/MYPOS01/pnl-history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["snapshots"][0]["estimated_pnl"] == 300.0

    def test_pnl_history_case_insensitive(self, client):
        now = int(time.time() * 1000)
        pnl_history.record("ABCDE", 41000.0, -50.0, 9, now)
        resp = client.get("/api/v1/positions/abcde/pnl-history")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_pnl_history_routing_not_shadowed(self, client):
        """/{pos_id}/pnl-history must not be shadowed by /{pos_id}."""
        resp = client.get("/api/v1/positions/ANYID/pnl-history")
        assert resp.status_code == 200
        assert "snapshots" in resp.json()


# ─── Auto-alert from SSE (via check endpoint) ─────────────────────────────────

class TestAutoAlertSSE:
    def test_price_alert_not_yet_triggered(self, client):
        # Create alert: BTC price > 50000 (current mock is 42000 → not triggered)
        client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 50000.0
        })
        resp = client.post("/api/v1/alerts/check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["newly_triggered"] == 0

    def test_price_alert_triggered_on_check(self, client):
        # Alert: BTC price > 40000, mock returns 42000 → triggered
        client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 40000.0
        })
        resp = client.post("/api/v1/alerts/check")
        assert resp.json()["newly_triggered"] == 1

    def test_triggered_alert_appears_in_list(self, client):
        client.post("/api/v1/alerts", json={
            "underlying": "ETH", "condition": "price_above", "threshold": 40000.0
        })
        client.post("/api/v1/alerts/check")
        resp = client.get("/api/v1/alerts/triggered")
        assert resp.json()["triggered_count"] >= 1

    def test_alert_not_double_fired(self, client):
        """Second check shouldn't re-fire an already-triggered alert."""
        client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 40000.0
        })
        r1 = client.post("/api/v1/alerts/check")
        r2 = client.post("/api/v1/alerts/check")
        assert r1.json()["newly_triggered"] == 1
        assert r2.json()["newly_triggered"] == 0  # already triggered
