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
