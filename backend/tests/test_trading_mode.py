import pytest
from unittest.mock import MagicMock, patch
from app.core.trading_mode import MODES, DEFAULT_MODE, TradingModeConfig


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
