import pytest
from unittest.mock import MagicMock, patch
from app.core.trading_mode import MODES, DEFAULT_MODE, TradingModeConfig


def test_get_default_mode(client):
    resp = client.get("/api/v1/config/trading-mode")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "swing"


def test_put_valid_mode(client):
    resp = client.put(
        "/api/v1/config/trading-mode",
        json={"name": "intraday"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "intraday"

    # Verify it persists in the subsequent GET
    resp2 = client.get("/api/v1/config/trading-mode")
    assert resp2.json()["name"] == "intraday"


def test_put_invalid_mode_400(client):
    resp = client.put(
        "/api/v1/config/trading-mode",
        json={"name": "unknown"},
    )
    assert resp.status_code == 400


def test_get_all_modes_has_four(client):
    resp = client.get("/api/v1/config/trading-mode/all")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    for name in ("scalping", "intraday", "swing", "positional"):
        assert name in data


def test_mode_persists_restart():
    with patch("app.services.db.set_trading_mode") as mock_set, \
         patch("app.services.db.get_trading_mode", return_value="scalping"):
        from app.core.trading_mode import MODES
        mode = MODES["scalping"]
        assert mode.name == "scalping"
        mock_set("scalping")
        mock_set.assert_called_once_with("scalping")


def test_all_modes_valid_configs():
    for name, cfg in MODES.items():
        assert isinstance(cfg, TradingModeConfig)
        assert cfg.name == name
        assert cfg.max_concurrent > 0
        assert cfg.poll_interval_s > 0
        assert 0 < cfg.position_pct < 1
        assert cfg.dte_min <= cfg.dte_max


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import create_app
    app = create_app()

    from app.core.trading_mode import MODES, DEFAULT_MODE
    app.state.trading_mode = MODES[DEFAULT_MODE]

    from unittest.mock import AsyncMock, MagicMock
    mock_adapter = AsyncMock()
    mock_adapter.ping = AsyncMock(return_value=True)
    app.state.adapter = mock_adapter

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
