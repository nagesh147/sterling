"""
Tests: session export/reset, alert input validation, health v2 fields, CI smoke tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle
from main import create_app


def _make_candles(n=100):
    return [Candle(timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                   open=40000.0+i*10, high=40050.0+i*10,
                   low=39950.0+i*10, close=40005.0+i*10, volume=100.0) for i in range(n)]


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


# ─── Session Export/Reset ─────────────────────────────────────────────────────

class TestSessionEndpoints:
    def test_export_returns_ok(self, client):
        resp = client.get("/api/v1/session/export")
        assert resp.status_code == 200

    def test_export_has_all_keys(self, client):
        data = client.get("/api/v1/session/export").json()
        for key in ["export_version", "export_timestamp_ms", "positions",
                    "alerts", "arrows", "eval_history", "pnl_history", "summary"]:
            assert key in data, f"Missing key: {key}"

    def test_export_summary_fields(self, client):
        summary = client.get("/api/v1/session/export").json()["summary"]
        for f in ["positions_open", "positions_closed",
                  "alerts_active", "alerts_triggered", "total_arrows"]:
            assert f in summary

    def test_export_version_is_string(self, client):
        data = client.get("/api/v1/session/export").json()
        assert isinstance(data["export_version"], str)

    def test_reset_returns_204(self, client):
        resp = client.delete("/api/v1/session/reset")
        assert resp.status_code == 204

    def test_reset_clears_alerts(self, client):
        client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 40000.0
        })
        assert client.get("/api/v1/alerts").json()["active_count"] == 1
        client.delete("/api/v1/session/reset")
        assert client.get("/api/v1/alerts").json()["active_count"] == 0

    def test_export_captures_alerts(self, client):
        client.post("/api/v1/alerts", json={
            "underlying": "ETH", "condition": "signal_green_arrow", "cooldown_hours": 2.0
        })
        data = client.get("/api/v1/session/export").json()
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["cooldown_hours"] == 2.0


# ─── Alert Input Validation ───────────────────────────────────────────────────

class TestAlertValidation:
    def test_price_above_requires_positive_threshold(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 0.0
        })
        assert resp.status_code == 422

    def test_price_above_requires_threshold(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above"
        })
        assert resp.status_code == 422

    def test_price_above_positive_ok(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 50000.0
        })
        assert resp.status_code == 200

    def test_ivr_above_requires_0_to_100(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "ivr_above", "threshold": 110.0
        })
        assert resp.status_code == 422

    def test_ivr_above_valid(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "ivr_above", "threshold": 70.0
        })
        assert resp.status_code == 200

    def test_ivr_below_zero_invalid(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "ivr_below", "threshold": -5.0
        })
        assert resp.status_code == 422

    def test_state_is_requires_target_state(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "state_is"
        })
        assert resp.status_code == 422

    def test_state_is_with_target_ok(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "state_is",
            "target_state": "CONFIRMED_SETUP_ACTIVE"
        })
        assert resp.status_code == 200

    def test_arrow_conditions_no_threshold_needed(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "ETH", "condition": "signal_green_arrow"
        })
        assert resp.status_code == 200

    def test_cooldown_max_168h(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "signal_red_arrow", "cooldown_hours": 200.0
        })
        assert resp.status_code == 422

    def test_cooldown_168h_ok(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "signal_red_arrow", "cooldown_hours": 168.0
        })
        assert resp.status_code == 200


# ─── Health v2 Fields ─────────────────────────────────────────────────────────

class TestHealthV2:
    def test_health_has_alerts_field(self, client):
        data = client.get("/health").json()
        assert "alerts" in data
        assert "active" in data["alerts"]
        assert "triggered" in data["alerts"]

    def test_health_has_uptime(self, client):
        data = client.get("/health").json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_health_background_checker_field(self, client):
        data = client.get("/health").json()
        assert data["background_checker"] == "running"

    def test_health_alerts_count_matches(self, client):
        client.post("/api/v1/alerts", json={
            "underlying": "SOL", "condition": "price_above", "threshold": 100.0
        })
        data = client.get("/health").json()
        assert data["alerts"]["active"] == 1

    def test_health_version_format(self, client):
        v = client.get("/health").json()["version"]
        parts = v.split(".")
        assert len(parts) == 3


# ─── CI Smoke Tests ───────────────────────────────────────────────────────────

class TestCISmoke:
    """Critical path tests — all must pass for CI to be green."""

    def test_app_boots(self, client):
        assert client.get("/health").status_code == 200

    def test_instruments_load(self, client):
        data = client.get("/api/v1/instruments").json()
        assert data["count"] >= 4

    def test_btc_has_options(self, client):
        inst = client.get("/api/v1/instruments/BTC").json()
        assert inst["options_available"] is True

    def test_run_once_returns_valid(self, client):
        data = client.post("/api/v1/directional/run-once?underlying=BTC").json()
        assert data["paper_mode"] is True
        assert "state" in data

    def test_watchlist_all_instruments(self, client):
        data = client.get("/api/v1/directional/watchlist").json()
        assert data["count"] >= 4

    def test_delta_india_account_active(self, client):
        info = client.get("/api/v1/account/info").json()
        assert info["active"] is True
        assert info["exchange_name"] == "delta_india"

    def test_paper_balances_available(self, client):
        data = client.get("/api/v1/account/balances").json()
        assert data["is_paper"] is True
        assert data["count"] > 0

    def test_session_export_works(self, client):
        data = client.get("/api/v1/session/export").json()
        assert data["summary"]["positions_open"] == 0

    def test_alerts_crud(self, client):
        crt = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 50000.0
        }).json()
        assert crt["status"] == "active"
        client.delete(f"/api/v1/alerts/{crt['id']}")
        assert client.get("/api/v1/alerts").json()["active_count"] == 0

    def test_positions_lifecycle(self, client):
        assert client.get("/api/v1/positions").json()["open_count"] == 0
        assert client.get("/api/v1/positions/greeks").json()["total_delta"] == 0.0
        assert client.get("/api/v1/positions/analytics").json()["total_closed"] == 0
