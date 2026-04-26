"""
Final tests: snapshot endpoint, timeout in RetryingAdapter, conftest isolation.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.schemas.market import Candle
from app.services.retry import RetryingAdapter
from app.services.exchanges.instrument_registry import get_instrument
from main import create_app


def _make_candles(n=100, base=40000.0, trend=10.0):
    return [
        Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=base + i * trend, high=base + i * trend + 50,
            low=base + i * trend - 50, close=base + i * trend + 5,
            volume=100.0,
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
    app = create_app()
    adapter = _mock_adapter()
    app.state.adapter = adapter
    with TestClient(app) as c:
        c.app.state.adapter = adapter
        yield c


# ─── Snapshot endpoint ────────────────────────────────────────────────────────

class TestSnapshotEndpoint:
    def test_snapshot_btc(self, client):
        resp = client.get("/api/v1/directional/snapshot?underlying=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert "spot_price" in data
        assert "macro_regime" in data
        assert "signal_trend" in data
        assert "state" in data
        assert "exec_mode" in data
        assert "ivr_band" in data

    def test_snapshot_eth(self, client):
        resp = client.get("/api/v1/directional/snapshot?underlying=ETH")
        assert resp.status_code == 200
        assert resp.json()["underlying"] == "ETH"

    def test_snapshot_unknown_404(self, client):
        resp = client.get("/api/v1/directional/snapshot?underlying=FAKE")
        assert resp.status_code == 404

    def test_snapshot_has_arrows(self, client):
        data = client.get("/api/v1/directional/snapshot?underlying=BTC").json()
        assert "green_arrow" in data
        assert "red_arrow" in data
        assert isinstance(data["green_arrow"], bool)

    def test_snapshot_st_trends_length(self, client):
        data = client.get("/api/v1/directional/snapshot?underlying=BTC").json()
        assert len(data["st_trends"]) == 3

    def test_snapshot_scores_in_range(self, client):
        data = client.get("/api/v1/directional/snapshot?underlying=BTC").json()
        assert 0.0 <= data["score_long"] <= 100.0
        assert 0.0 <= data["score_short"] <= 100.0
        assert 0.0 <= data["regime_score"] <= 100.0

    def test_snapshot_exec_confidence_in_range(self, client):
        data = client.get("/api/v1/directional/snapshot?underlying=BTC").json()
        assert 0.0 <= data["exec_confidence"] <= 1.0

    def test_snapshot_default_underlying(self, client):
        resp = client.get("/api/v1/directional/snapshot")
        assert resp.status_code == 200
        # Default is BTC from settings
        assert resp.json()["underlying"] == "BTC"


# ─── asyncio timeout in RetryingAdapter ───────────────────────────────────────

class TestRetryTimeout:
    """
    Tests retry logic when asyncio.TimeoutError occurs.
    Uses simulated TimeoutError (not real sleep) to keep suite fast.
    The RetryingAdapter wraps calls in asyncio.wait_for — these tests verify
    that the retry loop handles TimeoutError the same as any other exception.
    """

    @pytest.mark.asyncio
    async def test_retries_on_timeout_error(self):
        call_count = 0
        inner = MagicMock()

        async def timeout_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError("simulated timeout")
            return 42000.0

        inner.get_index_price = timeout_then_succeed
        # High call_timeout so asyncio.wait_for doesn't interfere —
        # we are testing the retry-on-TimeoutError path, not actual timing.
        adapter = RetryingAdapter(inner, max_attempts=3, base_delay=0.001, call_timeout=5.0)
        result = await adapter.get_index_price(get_instrument("BTC"))
        assert result == 42000.0
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_timeout_attempts(self):
        inner = MagicMock()

        async def always_timeout(*args, **kwargs):
            raise asyncio.TimeoutError("simulated")

        inner.get_index_price = always_timeout
        adapter = RetryingAdapter(inner, max_attempts=2, base_delay=0.001, call_timeout=5.0)
        with pytest.raises((asyncio.TimeoutError, Exception)):
            await adapter.get_index_price(get_instrument("BTC"))

    @pytest.mark.asyncio
    async def test_timeout_counted_as_attempt(self):
        """Each timeout counts as an attempt — max_attempts respected."""
        call_count = 0
        inner = MagicMock()

        async def always_timeout(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise asyncio.TimeoutError("simulated")

        inner.get_index_price = always_timeout
        adapter = RetryingAdapter(inner, max_attempts=3, base_delay=0.001, call_timeout=5.0)
        with pytest.raises(Exception):
            await adapter.get_index_price(get_instrument("BTC"))
        assert call_count == 3


# ─── conftest isolation ───────────────────────────────────────────────────────

class TestConftestIsolation:
    """Verify global stores reset between tests — these would fail if isolation breaks."""

    def test_positions_empty_at_start(self, client):
        from app.services import paper_store
        assert len(paper_store._positions) == 0

    def test_history_empty_at_start(self):
        from app.services import eval_history
        assert eval_history.get_history("BTC") == []

    def test_positions_still_empty_in_next_test(self, client):
        from app.services import paper_store
        assert len(paper_store._positions) == 0


# ─── startup health check visible via /health ─────────────────────────────────

class TestHealthFinal:
    def test_health_exchange_adapter_field(self, client):
        data = client.get("/health").json()
        assert data["exchange_adapter"] in ("deribit", "okx")

    def test_health_cache_keys_field(self, client):
        data = client.get("/health").json()
        # cache_keys may be None if adapter doesn't have _cache
        assert "cache_keys" in data

    def test_health_version_format(self, client):
        version = client.get("/health").json()["version"]
        parts = version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
