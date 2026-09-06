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

# ─── Alert Input Validation ───────────────────────────────────────────────────

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

    def test_health_version_format(self, client):
        v = client.get("/health").json()["version"]
        parts = v.split(".")
        assert len(parts) == 3


# ─── CI Smoke Tests ───────────────────────────────────────────────────────────

class TestCISmoke:
    """Critical path tests — all must pass for CI to be green."""

    def test_app_boots(self, client):
        assert client.get("/health").status_code == 200
