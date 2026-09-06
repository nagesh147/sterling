import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.config import router
from app.services import db


@pytest.fixture(autouse=True)
def isolated_db():
    """These cases assert DEFAULTS, so they must not read persisted config.

    Without this they passed only by accident: a fixture in another api test
    file left `db._DB_PATH` pointing at a temp file it had already deleted, so
    every config read fell back to the default. Once that leak was fixed these
    started reading the developer's real database, where the engine may well be
    switched off. Own the isolation here instead of depending on someone else's
    bug.
    """
    prior_path = db._DB_PATH
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    try:
        yield
    finally:
        db._DB_PATH = prior_path
        db.init()
        if os.path.exists(path):
            os.unlink(path)


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_orb_config_is_disabled_on_a_fresh_install():
    """Power switch, off until an operator turns it on.

    Auto-off is a second, orthogonal gate: even with the engine on,
    ``execute_scan`` returns ``status=manual`` and places nothing.
    """
    response = client().get("/api/v1/config/nifty-orb-options")
    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["enabled"] is False
    assert payload["defaults"]["enabled"] is False
    assert payload["config"]["execution_broker"] == "kite"
    assert payload["supported_data_sources"] == ["kite", "truedata"]
    assert payload["execution_brokers"] == ["kite"]


def test_orb_config_publishes_the_engines_own_defaults():
    """The board marks which fields are still at default off this payload.

    A second copy of the defaults in the client is the drift this codebase keeps
    hitting, so the endpoint must publish them and they must cover every field.
    """
    import json

    from app.engines.nifty_orb_options import StrategyConfig

    payload = client().get("/api/v1/config/nifty-orb-options").json()
    defaults = payload["defaults"]
    # through JSON, so the engine's tuples arrive as lists -- compare like for like
    assert defaults == json.loads(json.dumps(StrategyConfig().__dict__))
    assert set(defaults) == set(payload["config"])


def test_the_published_defaults_are_themselves_valid():
    """Reset-to-defaults must not hand the engine a config it would reject."""
    from app.engines.nifty_orb_options import StrategyConfig

    defaults = client().get("/api/v1/config/nifty-orb-options").json()["defaults"]
    StrategyConfig(**defaults).validate()


def test_orb_does_not_own_a_paper_live_control():
    """Paper/Live and Manual/Auto belong to the universal trading mode.

    A strategy-local ``paper_only`` flag would let the UI claim a safety the
    shared execution path never reads.
    """
    config = client().get("/api/v1/config/nifty-orb-options").json()["config"]
    assert "paper_only" not in config
    assert not [k for k in config if "paper" in k or "live" in k]


def test_orb_config_rejects_a_zero_volume_multiplier():
    """Zero used to disable the volume gate and divide by zero downstream."""
    response = client().put("/api/v1/config/nifty-orb-options", json={"volume_multiplier": 0})
    assert response.status_code == 422
    assert "volume_multiplier" in response.json()["detail"]


def test_orb_config_rejects_an_inverted_dte_range():
    response = client().put(
        "/api/v1/config/nifty-orb-options",
        json={"expiry_dte_min": 5, "expiry_dte_max": 2},
    )
    assert response.status_code == 422
    assert "expiry_dte_max" in response.json()["detail"]


def test_orb_config_rejects_non_kite_execution():
    response = client().put(
        "/api/v1/config/nifty-orb-options",
        json={"execution_broker": "truedata"},
    )
    assert response.status_code == 422
    assert "fixed to 'kite'" in response.json()["detail"]


def test_orb_backtest_requires_ohlcv_list():
    response = client().post(
        "/api/v1/config/nifty-orb-options/backtest",
        json={"bars": "not-a-list"},
    )
    assert response.status_code == 422
    assert "bars must be a list" in response.json()["detail"]


def test_orb_config_rejects_a_strategy_local_auto_flag():
    """Manual/Auto is Trading Mode. A PUT must 422, not silently ignore."""
    response = client().put("/api/v1/config/nifty-orb-options", json={"auto_execute": True})
    assert response.status_code == 422
    detail = response.json()["detail"]
    text = detail if isinstance(detail, str) else str(detail)
    assert "auto_execute" in text


def test_orb_config_rejects_a_strategy_local_paper_flag():
    response = client().put("/api/v1/config/nifty-orb-options", json={"paper_only": True})
    assert response.status_code == 422
    detail = response.json()["detail"]
    text = detail if isinstance(detail, str) else str(detail)
    assert "paper_only" in text


def test_orb_execute_returns_manual_and_does_not_place(monkeypatch):
    """`/execute` used to call place_manual_order. Manual Buy is the board ticket."""
    placed: list = []

    async def boom(*a, **k):
        placed.append(1)
        raise AssertionError("execute must not place")

    monkeypatch.setattr("app.services.kite_engine.service.place_manual_order", boom, raising=False)
    response = client().post("/api/v1/config/nifty-orb-options/execute")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "manual"
    assert payload["executed"] == []
    assert placed == []
