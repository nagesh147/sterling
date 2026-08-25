"""API tests for Smart Money Multi-X Options endpoints."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.v1.endpoints.config import router


def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_get_smart_money_options_descriptor():
    res = client().get("/api/v1/config/smart-money-options")
    assert res.status_code == 200
    data = res.json()
    assert data["strategy"]["id"] == "smart_money_options"
    assert data["strategy"]["name"] == "Smart Money Multi-X Options"
    assert "strike_selection" in data["vocabularies"]
    assert "OTM1" in data["vocabularies"]["strike_selection"]
    assert data["defaults"]["target_multiplier_3"] == 5.0


def test_put_smart_money_options_config():
    c = client()
    res = c.put("/api/v1/config/smart-money-options", json={"min_consolidation_bars": 12, "volume_surge_multiplier": 2.2})
    assert res.status_code == 200
    cfg = res.json()["config"]
    assert cfg["min_consolidation_bars"] == 12
    assert cfg["volume_surge_multiplier"] == 2.2


def test_get_snapshot_and_scan():
    c = client()
    snap = c.get("/api/v1/config/smart-money-options/snapshot")
    assert snap.status_code == 200
    snap_data = snap.json()
    assert snap_data["strategy_id"] == "smart_money_options"
    assert isinstance(snap_data["signals"], list)

    scan = c.post("/api/v1/config/smart-money-options/scan")
    assert scan.status_code == 200
    assert scan.json()["scanned"] >= 1
