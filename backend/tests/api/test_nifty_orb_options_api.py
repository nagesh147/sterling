from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.config import router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_orb_config_is_enabled_by_default():
    """A power switch, not a safety device.

    For THIS engine that is a stronger statement than for the others: its runner
    gates on `enabled` and the market clock and then executes, with no
    `auto_execute` check — so `account.is_paper` is what stands between it and
    real orders.
    """
    response = client().get("/api/v1/config/nifty-orb-options")
    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["enabled"] is True
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
