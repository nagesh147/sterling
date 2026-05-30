"""GET/POST /derivatives/edge-gate — operator-tunable edge gate.

Lets the UI adjust the (min_net_return, min_sharpe, min_trades) thresholds that
decide which backtest combos may emit live edge signals, and see how many
combos the current gate admits.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.derivatives import router as derivatives_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(derivatives_router, prefix="/api/v1")
    return TestClient(app)


def test_get_returns_default_gate_and_admitted(client):
    r = client.get("/api/v1/derivatives/edge-gate")
    assert r.status_code == 200
    body = r.json()
    assert body["gate"]["min_sharpe"] == 0.8
    assert body["gate"]["min_trades"] == 50
    assert body["gate"]["min_net_return"] == 0.0
    # Real CSV at repo root → some 4h combos admitted by default.
    assert body["admitted_count"] >= 1
    assert all(c["tf"] == "4h" for c in body["admitted"])
    assert body["admitted_count"] == len(body["admitted"])


def test_post_loosening_admits_more_and_persists(client):
    strict = client.get("/api/v1/derivatives/edge-gate").json()["admitted_count"]
    r = client.post("/api/v1/derivatives/edge-gate",
                    json={"min_net_return": 0.0, "min_sharpe": 0.0, "min_trades": 50})
    assert r.status_code == 200
    loose = r.json()
    assert loose["gate"]["min_sharpe"] == 0.0
    assert loose["admitted_count"] >= strict
    # persisted: a subsequent GET reflects the new gate
    again = client.get("/api/v1/derivatives/edge-gate").json()
    assert again["gate"]["min_sharpe"] == 0.0
    assert again["admitted_count"] == loose["admitted_count"]


def test_post_tightening_can_empty_the_feed(client):
    r = client.post("/api/v1/derivatives/edge-gate",
                    json={"min_net_return": 0.0, "min_sharpe": 0.8, "min_trades": 10_000_000})
    assert r.status_code == 200
    assert r.json()["admitted_count"] == 0


def test_post_validates_ranges(client):
    # negative min_trades is nonsensical → 422
    r = client.post("/api/v1/derivatives/edge-gate",
                    json={"min_net_return": 0.0, "min_sharpe": 0.8, "min_trades": -5})
    assert r.status_code == 422
