"""
Tests for: SQLite persistence, RetryingAdapter, monitoring endpoints, portfolio summary.
"""
import time
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.schemas.market import Candle
from app.schemas.execution import TradeStructure, SizedTrade
from app.schemas.directional import Direction
from app.services.retry import RetryingAdapter
from app.services.exchanges.instrument_registry import get_instrument
from main import create_app


def _make_candles(n=100, base=40000.0):
    return [
        Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=base + i * 10, high=base + i * 10 + 50,
            low=base + i * 10 - 50, close=base + i * 10 + 5, volume=100.0,
        )
        for i in range(n)
    ]


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=_make_candles())
    a.get_option_chain = AsyncMock(return_value=[])
    a.get_dvol = AsyncMock(return_value=55.0)
    a.get_dvol_history = AsyncMock(return_value=[40.0, 55.0, 70.0])
    a.close = AsyncMock(return_value=None)
    return a


@pytest.fixture()
def client():
    from app.services import paper_store
    paper_store._positions.clear()
    paper_store._loaded = True  # skip SQLite bootstrap in tests
    app = create_app()
    adapter = _mock_adapter()
    app.state.adapter = adapter
    with TestClient(app) as c:
        c.app.state.adapter = adapter
        yield c
    paper_store._positions.clear()


# ─── RetryingAdapter ──────────────────────────────────────────────────────────

class TestRetryingAdapter:
    def _inner_failing(self, fail_times: int = 2):
        call_count = 0
        inner = MagicMock()
        async def flaky(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= fail_times:
                raise ConnectionError("transient")
            return 42000.0
        inner.get_index_price = flaky
        inner.close = AsyncMock()
        return inner, lambda: call_count

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        inner, count = self._inner_failing(fail_times=1)
        adapter = RetryingAdapter(inner, max_attempts=3, base_delay=0.001)  # fast delay
        inst = get_instrument("BTC")
        result = await adapter.get_index_price(inst)
        assert result == 42000.0
        assert count() == 2  # failed once, succeeded on second

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        inner, _ = self._inner_failing(fail_times=99)
        adapter = RetryingAdapter(inner, max_attempts=2, base_delay=0.001)
        inst = get_instrument("BTC")
        with pytest.raises(ConnectionError):
            await adapter.get_index_price(inst)

    @pytest.mark.asyncio
    async def test_dvol_returns_none_on_failure(self):
        inner = MagicMock()
        inner.get_dvol = AsyncMock(side_effect=RuntimeError("dvol gone"))
        adapter = RetryingAdapter(inner, max_attempts=2, base_delay=0.01)
        result = await adapter.get_dvol(get_instrument("BTC"))
        assert result is None

    @pytest.mark.asyncio
    async def test_dvol_history_returns_empty_on_failure(self):
        inner = MagicMock()
        inner.get_dvol_history = AsyncMock(side_effect=RuntimeError("gone"))
        adapter = RetryingAdapter(inner, max_attempts=2, base_delay=0.01)
        result = await adapter.get_dvol_history(get_instrument("BTC"))
        assert result == []

    @pytest.mark.asyncio
    async def test_ping_returns_false_on_failure(self):
        inner = MagicMock()
        inner.ping = AsyncMock(side_effect=Exception("down"))
        adapter = RetryingAdapter(inner, max_attempts=2, base_delay=0.01)
        assert not await adapter.ping()


# ─── SQLite db module ─────────────────────────────────────────────────────────

class TestDBModule:
    def test_init_with_memory_path(self, tmp_path):
        import os
        from app.services import db as db_mod
        db_path = str(tmp_path / "test.db")
        original = db_mod._DB_PATH
        db_mod._DB_PATH = db_path
        db_mod._available = False
        try:
            assert db_mod.init() is True
            assert db_mod._available is True
        finally:
            db_mod._DB_PATH = original
            db_mod._available = False

    def test_upsert_and_load(self, tmp_path):
        from app.services import db as db_mod
        db_path = str(tmp_path / "pos.db")
        original_path = db_mod._DB_PATH
        original_avail = db_mod._available
        db_mod._DB_PATH = db_path
        db_mod.init()
        try:
            pos_dict = {
                "id": "TESTPOS1", "underlying": "BTC", "status": "open",
                "entry_timestamp_ms": int(time.time() * 1000),
                "sized_trade": {}, "notes": "", "run_once_state": "ENTERED",
                "entry_spot_price": 42000.0,
            }
            db_mod.upsert(pos_dict)
            loaded = db_mod.load_all()
            assert len(loaded) == 1
            assert loaded[0]["id"] == "TESTPOS1"
        finally:
            db_mod._DB_PATH = original_path
            db_mod._available = original_avail

    def test_remove(self, tmp_path):
        from app.services import db as db_mod
        db_path = str(tmp_path / "pos2.db")
        original_path, original_avail = db_mod._DB_PATH, db_mod._available
        db_mod._DB_PATH = db_path
        db_mod.init()
        try:
            pos_dict = {
                "id": "TODELETE", "underlying": "ETH", "status": "open",
                "entry_timestamp_ms": int(time.time() * 1000),
                "sized_trade": {}, "notes": "", "run_once_state": "ENTERED",
                "entry_spot_price": 3000.0,
            }
            db_mod.upsert(pos_dict)
            db_mod.remove("TODELETE")
            assert db_mod.load_all() == []
        finally:
            db_mod._DB_PATH = original_path
            db_mod._available = original_avail


# ─── Portfolio Summary ────────────────────────────────────────────────────────

class TestPortfolioSummary:
    def test_empty_summary(self, client):
        resp = client.get("/api/v1/positions/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["open_count"] == 0
        assert data["closed_count"] == 0
        assert data["total_open_risk_usd"] == 0.0
        assert data["total_realized_pnl_usd"] == 0.0

    def test_summary_fields(self, client):
        resp = client.get("/api/v1/positions/summary")
        data = resp.json()
        for field in ["open_count", "closed_count", "total_positions",
                      "total_open_risk_usd", "total_realized_pnl_usd",
                      "largest_open_risk_usd", "underlyings_open",
                      "avg_capital_at_risk_pct", "timestamp_ms"]:
            assert field in data, f"Missing field: {field}"


# ─── Monitor Endpoints ────────────────────────────────────────────────────────

class TestMonitorEndpoints:
    def test_monitor_unknown_404(self, client):
        resp = client.post("/api/v1/positions/DEADBEEF/monitor")
        assert resp.status_code == 404

    def test_monitor_all_empty(self, client):
        resp = client.post("/api/v1/positions/monitor-all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["open_positions_checked"] == 0
        assert data["exit_recommended"] == []
        assert data["partial_recommended"] == []


# ─── Enhanced Health ──────────────────────────────────────────────────────────

class TestEnhancedHealth:
    def test_health_has_new_fields(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "exchange_adapter" in data
        assert "positions" in data
        assert "exchange_reachable" in data
        assert data["positions"]["open"] == 0
        assert data["positions"]["closed"] == 0

    def test_health_exchange_reachable(self, client):
        resp = client.get("/health")
        # Mock ping returns True
        assert resp.json()["exchange_reachable"] is True
