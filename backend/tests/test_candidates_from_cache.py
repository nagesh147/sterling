"""Candidate endpoints serve the background scanner's cache, never a live scan.

Root-cause fix for the wedged-server bug: `/candidates/futures` and
`/candidates/options` used to run a ~4.6s synchronous full-universe scalping
scan directly on the asyncio event loop on every poll. The FE polls both every
30s and the background scanner ticks every 30s — saturating the single loop and
hanging the whole server. Now the scanner is the only producer (off-thread) and
the endpoints are trivial cache reads.
"""
from __future__ import annotations

import inspect

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import derivatives as D
from app.api.v1.endpoints.derivatives import router as derivatives_router


def _row(signal_id, strategy, underlying, leg):
    return {
        "signal_id": signal_id,
        "source": "edge" if strategy.startswith("edge/") else "engine",
        "strategy": strategy,
        "underlying": underlying, "direction": "long", "instrument_type": leg,
        "contracts": 1.0, "leverage": 5.0, "notional_usd": 1000.0,
        "expected_r": 2.0, "freeze_token": f"tok-{signal_id}",
        "freeze_token_ttl_ms": 30000, "status": "ok", "reason": "ok",
    }


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(derivatives_router, prefix="/api/v1")
    app.state.derivatives_scan_cache = {
        "futures": [
            _row("edge:BTCUSD:4h:smc", "edge/smc", "BTCUSD", "futures"),
            _row("scalp:ETHUSD:pa", "scalping/price_action", "ETHUSD", "futures"),
        ],
        "options": [
            _row("edge:BTCUSD:4h:smc", "edge/smc", "BTCUSD", "options"),
        ],
        "last_scan_ms": 1234,
        "next_scan_ms": 31234,
    }
    return TestClient(app)


def test_collect_armed_signals_is_synchronous():
    # Must be a plain function so it can be offloaded via asyncio.to_thread.
    assert not inspect.iscoroutinefunction(D._collect_armed_signals)


def test_futures_endpoint_serves_cache(client):
    r = client.get("/api/v1/derivatives/candidates/futures")
    assert r.status_code == 200
    body = r.json()
    assert {c["signal_id"] for c in body["candidates"]} == {"edge:BTCUSD:4h:smc", "scalp:ETHUSD:pa"}
    assert all(c["instrument_type"] == "futures" for c in body["candidates"])
    assert body["timestamp_ms"] == 1234


def test_options_endpoint_serves_cache(client):
    r = client.get("/api/v1/derivatives/candidates/options")
    assert r.status_code == 200
    ids = {c["signal_id"] for c in r.json()["candidates"]}
    assert ids == {"edge:BTCUSD:4h:smc"}


def test_endpoint_filters_by_strategy_and_underlying(client):
    r = client.get("/api/v1/derivatives/candidates/futures?strategy=edge/smc")
    assert {c["signal_id"] for c in r.json()["candidates"]} == {"edge:BTCUSD:4h:smc"}
    r2 = client.get("/api/v1/derivatives/candidates/futures?underlying=ETHUSD")
    assert {c["signal_id"] for c in r2.json()["candidates"]} == {"scalp:ETHUSD:pa"}


def test_edge_rows_bypass_strategy_filter(client):
    """Edge is a cross-strategy validated feed — its rows must show on EVERY
    tab, even one scoped to another strategy (e.g. directional), so the operator
    never misses a proven signal. Engine rows still respect the filter."""
    r = client.get("/api/v1/derivatives/candidates/futures?strategy=directional")
    ids = {c["signal_id"] for c in r.json()["candidates"]}
    assert ids == {"edge:BTCUSD:4h:smc"}        # edge shown; scalping filtered out


def test_edge_rows_still_respect_underlying_filter(client):
    # Bypassing the strategy filter must NOT bypass the underlying filter.
    r = client.get("/api/v1/derivatives/candidates/futures?strategy=directional&underlying=ETHUSD")
    assert r.json()["candidates"] == []          # edge row is BTC, filtered by underlying


def test_endpoint_never_runs_live_scan(client, monkeypatch):
    """The decisive root-cause guard: even if the live scan would crash, the
    endpoint still answers from cache — proving it does NO per-request scan."""
    def _boom(*a, **k):
        raise AssertionError("live scan must NOT run on a candidate request")
    monkeypatch.setattr(D, "_collect_armed_signals", _boom)
    r = client.get("/api/v1/derivatives/candidates/futures")
    assert r.status_code == 200
    assert len(r.json()["candidates"]) == 2


def test_missing_cache_returns_empty():
    app = FastAPI()
    app.include_router(derivatives_router, prefix="/api/v1")
    c = TestClient(app)
    r = c.get("/api/v1/derivatives/candidates/futures")
    assert r.status_code == 200
    assert r.json()["candidates"] == []
