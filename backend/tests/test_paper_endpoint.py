"""Read-only paper-book demo endpoint — file-backed, isolated from study.*."""
from __future__ import annotations

import csv
import json
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.v1.endpoints.paper as paper_mod
from app.api.v1.endpoints.paper import router as paper_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(paper_mod, "PAPER_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(paper_router, prefix="/api/v1")
    return TestClient(app)


def _write_state(tmp_path):
    state = {
        "total_equity": 889.02, "capital": 500.0, "n_closed": 146,
        "inception": "2025-09-07T00:00:00", "asof": "2026-06-10T08:00:00",
        "realized": {"end": 857.76, "ret": 0.7155, "sharpe": 2.35,
                     "max_dd": -0.2986, "n": 3,
                     "weighted_pnls": [0.10, -0.05, 0.08]},
        "open_positions": [{"symbol": "BTCUSD", "direction": "short",
                            "unrealized_pnl": 0.0375}],
        "breaker": {"peak": 889.02, "drawdown": 0.05, "tripped": False,
                    "threshold": 0.25, "recover": 0.10},
    }
    (tmp_path / "state.json").write_text(json.dumps(state))


def test_state_missing_is_available_false_not_500(client):
    r = client.get("/api/v1/paper/state")
    assert r.status_code == 200
    assert r.json()["available"] is False


def test_state_returns_derived_fields(client, tmp_path):
    _write_state(tmp_path)
    r = client.get("/api/v1/paper/state")
    assert r.status_code == 200
    b = r.json()
    assert b["available"] is True
    assert b["return_pct"] == pytest.approx(77.8, abs=0.1)        # 889.02/500-1
    assert b["buffer_to_trip"] == pytest.approx(20.0, abs=0.1)    # (0.25-0.05)*100
    assert b["tripped"] is False
    # equity_curve = cumprod(1+wp)*capital: 500*1.10=550, *0.95=522.5, *1.08=564.3
    assert b["equity_curve"][0] == pytest.approx(550.0, abs=0.1)
    assert b["equity_curve"][-1] == pytest.approx(564.3, abs=0.2)
    assert b["realized"]["sharpe"] == pytest.approx(2.35)
    assert len(b["open_positions"]) == 1


def test_paper_module_does_not_import_study(client):
    # Isolation invariant: the endpoint reads files, never imports study code.
    assert not any(m == "study" or m.startswith("study.") for m in sys.modules), \
        "paper endpoint must not import any study.* module"
