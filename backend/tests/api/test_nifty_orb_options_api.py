from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.config import router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_orb_config_is_disabled_and_paper_only_by_default():
    response = client().get("/api/v1/config/nifty-orb-options")
    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["enabled"] is False
    assert payload["config"]["paper_only"] is True
    assert payload["config"]["execution_broker"] == "kite"
    assert payload["supported_data_sources"] == ["kite", "truedata"]
    assert payload["execution_brokers"] == ["kite"]


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
