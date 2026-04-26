"""
Tests: CSV export endpoints, conftest isolation for exchange store.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle
from main import create_app


def _make_candles(n=100):
    return [Candle(
        timestamp_ms=1_700_000_000_000 + i * 3_600_000,
        open=40000.0 + i * 10, high=40050.0 + i * 10,
        low=39950.0 + i * 10, close=40005.0 + i * 10, volume=100.0,
    ) for i in range(n)]


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


class TestCSVExport:
    def test_fills_csv_returns_csv(self, client):
        resp = client.get("/api/v1/account/fills/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        assert "fill_id" in content  # header row

    def test_account_positions_csv(self, client):
        resp = client.get("/api/v1/account/positions/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "symbol" in resp.text

    def test_paper_positions_csv(self, client):
        resp = client.get("/api/v1/positions/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        content = resp.text
        assert "underlying" in content

    def test_paper_positions_csv_status_filter(self, client):
        resp = client.get("/api/v1/positions/export?status=open")
        assert resp.status_code == 200

    def test_fills_csv_has_content_disposition(self, client):
        resp = client.get("/api/v1/account/fills/export")
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert ".csv" in cd

    def test_fills_csv_paper_mode_has_header_only(self, client):
        # Paper mode returns empty fills, CSV should have only header
        resp = client.get("/api/v1/account/fills/export")
        lines = [l for l in resp.text.strip().split("\n") if l]
        assert len(lines) == 1  # only header
        assert "fill_id" in lines[0]


class TestConftestExchangeIsolation:
    """Verify exchange store resets between tests."""

    def test_exchange_store_has_delta_india(self, client):
        from app.services import exchange_account_store as eas
        configs = eas.list_exchanges()
        names = [c.name for c in configs]
        assert "delta_india" in names

    def test_exchange_store_fresh_each_test_a(self, client):
        from app.services import exchange_account_store as eas
        initial_count = len(eas.list_exchanges())
        eas.add_exchange(__import__('app.schemas.exchange_config', fromlist=['ExchangeConfigCreate']).ExchangeConfigCreate(
            name="okx", display_name="OKX test", api_key="k", api_secret="s", is_paper=True
        ))
        assert len(eas.list_exchanges()) == initial_count + 1

    def test_exchange_store_fresh_each_test_b(self, client):
        # If isolation works, OKX from previous test should NOT be here
        from app.services import exchange_account_store as eas
        names = [c.name for c in eas.list_exchanges()]
        # Only delta_india default — no OKX from previous test
        assert names.count("okx") == 0

    def test_account_endpoints_use_active_exchange(self, client):
        resp = client.get("/api/v1/account/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is True
        assert data["exchange_name"] == "delta_india"
