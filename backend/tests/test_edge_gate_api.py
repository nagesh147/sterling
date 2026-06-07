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


def test_get_default_gate_is_deflation_strict_and_admits_nothing(client):
    r = client.get("/api/v1/derivatives/edge-gate")
    assert r.status_code == 200
    body = r.json()
    # Deflation-first default gate: raw in-sample Sharpe relaxed to 0, but the
    # combo must clear the deflated Sharpe (≥ 0.5, multiple-testing corrected
    # over the whole grid) AND beat buy-and-hold. See derivatives._edge_gate.
    assert body["gate"]["min_sharpe"] == 0.0
    assert body["gate"]["min_trades"] == 20
    assert body["gate"]["min_dsr"] == 0.5
    assert body["gate"]["require_beats_hold"] is True
    # Honest tripwire: with the current strategy zoo NOTHING survives deflation
    # (best DSR ≈ 0.10 ≪ 0.5), so the live feed admits zero. The day a strategy
    # finally clears the bar this flips — which is the signal you want.
    assert body["admitted_count"] == 0
    assert body["admitted_count"] == len(body["admitted"])
    # Invariant regardless of data: anything admitted satisfies the gate.
    assert all(c["dsr"] >= 0.5 and c["beats_hold"] for c in body["admitted"])


def test_post_loosening_admits_more_and_persists(client):
    strict = client.get("/api/v1/derivatives/edge-gate").json()["admitted_count"]
    # Drop deflation + buy-and-hold + robustness floors for research/exploration.
    r = client.post("/api/v1/derivatives/edge-gate",
                    json={"min_net_return": 0.0, "min_sharpe": 0.0, "min_trades": 20,
                          "min_oos_sharpe": -100.0, "max_p_loss": 1.0,
                          "min_dsr": 0.0, "require_beats_hold": False})
    assert r.status_code == 200
    loose = r.json()
    assert loose["gate"]["min_dsr"] == 0.0
    assert loose["gate"]["require_beats_hold"] is False
    # Loosening admits the net-profitable configs the strict gate filtered out.
    assert loose["admitted_count"] >= 1
    assert loose["admitted_count"] > strict
    assert all(c["tf"] in {"15m", "30m", "1h", "2h", "4h"} for c in loose["admitted"])
    # persisted: a subsequent GET reflects the new gate
    again = client.get("/api/v1/derivatives/edge-gate").json()
    assert again["gate"]["min_dsr"] == 0.0
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
