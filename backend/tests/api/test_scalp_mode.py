from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from app.services import adapter_manager


@pytest.mark.asyncio
async def test_get_and_set_scalp_mode():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        mock_start = AsyncMock()
        mock_stop = AsyncMock()
        app.state.start_crypto_services = mock_start
        app.state.stop_crypto_services = mock_stop
        app.state.scalp_mode = False

        res = await client.get("/api/v1/trading/scalp-mode")
        assert res.status_code == 200
        assert res.json()["enabled"] is False

        res = await client.post("/api/v1/trading/scalp-mode", json={"enabled": True})
        assert res.status_code == 200
        assert res.json()["enabled"] is True
        assert app.state.scalp_mode is True
        mock_start.assert_awaited_once_with(app)
        mock_stop.assert_not_awaited()

        mock_start.reset_mock()
        res = await client.post("/api/v1/trading/scalp-mode", json={"enabled": False})
        assert res.status_code == 200
        assert res.json()["enabled"] is False
        assert app.state.scalp_mode is False
        mock_stop.assert_awaited_once_with(app)
        mock_start.assert_not_awaited()


@pytest.mark.asyncio
async def test_adapter_manager_init_gated():
    with patch("app.services.adapter_manager._build_raw") as mock_build:
        raw_mock = AsyncMock()
        raw_mock.start_ws = AsyncMock()
        raw_mock.stop_ws = AsyncMock()
        mock_build.return_value = raw_mock

        await adapter_manager.init("delta_india", start_ws=False)
        raw_mock.start_ws.assert_not_awaited()

        await adapter_manager.init("delta_india", start_ws=True)
        raw_mock.start_ws.assert_awaited_once()

        await adapter_manager.stop_feed()
        raw_mock.stop_ws.assert_awaited_once()
