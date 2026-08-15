from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.adaptive_edge import router


def test_settings_round_trip_and_snapshot_shape():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    got = client.get("/api/v1/adaptive-edge/settings")
    assert got.status_code == 200
    assert got.json()["live_trading"] is False
    body = got.json()["settings"]
    body["stop_points"] = 90
    put = client.put("/api/v1/adaptive-edge/settings", json=body)
    assert put.status_code == 200
    assert put.json()["settings"]["stop_points"] == 90
    snap = client.get("/api/v1/adaptive-edge/snapshot")
    assert snap.status_code == 200
    payload = snap.json()
    assert payload["live_trading"] is False
    assert payload["production_gate_authorized"] is False
    assert "session" in payload
    assert "readiness" in payload
    assert "mode_counts" in payload
    assert "formula_table" in payload
    assert "signals" in payload
    assert payload["production_gate_authorized"] is False


def test_settings_accepts_universe_and_ladder():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    body = client.get("/api/v1/adaptive-edge/settings").json()["settings"]
    body["scan_indices"] = ["NIFTY 50", "NIFTY BANK"]
    body["strike_moneyness"] = ["ITM2", "ITM1", "ATM", "OTM1", "OTM2"]
    put = client.put("/api/v1/adaptive-edge/settings", json=body)
    assert put.status_code == 200
    assert put.json()["live_trading"] is False
    assert put.json()["settings"]["strike_moneyness"] == ["ITM2", "ITM1", "ATM", "OTM1", "OTM2"]
    assert put.json()["settings"]["symbols"] == ["NIFTY-I", "BANKNIFTY-I"]
    assert put.json()["settings"]["symbol"] == "NIFTY-I"


def test_settings_accepts_engine_scope_fields():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    body = client.get("/api/v1/adaptive-edge/settings").json()["settings"]
    body["scan_source"] = "spot"
    body["scan_stock_contracts"] = False
    body["scan_all_stocks"] = False
    body["scan_stocks"] = []
    body["scan_expiries_indices"] = ["weekly", "monthly"]
    put = client.put("/api/v1/adaptive-edge/settings", json=body)
    assert put.status_code == 200
    saved = put.json()["settings"]
    assert saved["scan_source"] == "spot"
    assert saved["scan_stock_contracts"] is False
    assert saved["scan_expiries"] == ["weekly", "monthly"]
    assert put.json()["live_trading"] is False
