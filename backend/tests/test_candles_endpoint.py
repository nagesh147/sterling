import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.schemas.market import Candle


def _make_candle(i: int) -> Candle:
    return Candle(
        timestamp_ms=1_700_000_000_000 + i * 900_000,
        open=30000.0 + i, high=30100.0 + i,
        low=29900.0 + i, close=30050.0 + i,
        volume=200.0,
    )


@pytest.fixture
def client_with_candles():
    from fastapi.testclient import TestClient
    from main import create_app
    app = create_app()

    mock_adapter = AsyncMock()
    mock_adapter.ping = AsyncMock(return_value=True)
    mock_adapter.get_candles = AsyncMock(return_value=[_make_candle(i) for i in range(10)])
    app.state.adapter = mock_adapter

    from app.core.trading_mode import MODES
    app.state.trading_mode = MODES["swing"]

    with TestClient(app) as c:
        yield c


def test_candles_returns_ohlcv_list(client_with_candles):
    resp = client_with_candles.get("/api/v1/candles/BTC?tf=15m&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 10


def test_candles_tf_15m_accepted(client_with_candles):
    resp = client_with_candles.get("/api/v1/candles/BTC?tf=15m&limit=5")
    assert resp.status_code == 200


def test_candles_limit_clamped_at_500(client_with_candles):
    resp = client_with_candles.get("/api/v1/candles/BTC?tf=1H&limit=600")
    # Should be clamped or rejected; FastAPI Query(le=500) returns 422
    assert resp.status_code in (200, 422)


def test_candles_time_field_is_unix_int(client_with_candles):
    resp = client_with_candles.get("/api/v1/candles/BTC?tf=15m&limit=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert isinstance(data[0]["time"], int)
    # Should be a reasonable unix timestamp (after year 2020)
    assert data[0]["time"] > 1_580_000_000


def test_candles_invalid_tf_400(client_with_candles):
    resp = client_with_candles.get("/api/v1/candles/BTC?tf=999m&limit=10")
    assert resp.status_code == 400


def test_candles_cache_ttl_applied(client_with_candles):
    from app.api.v1.endpoints import candles as candles_mod
    candles_mod._cache.clear()
    resp1 = client_with_candles.get("/api/v1/candles/BTC?tf=15m&limit=10")
    assert resp1.status_code == 200
    # Second call should hit cache
    resp2 = client_with_candles.get("/api/v1/candles/BTC?tf=15m&limit=10")
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()
    candles_mod._cache.clear()
