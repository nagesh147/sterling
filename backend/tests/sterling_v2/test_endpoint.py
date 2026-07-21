import math

import pytest
from fastapi.testclient import TestClient
from main import create_app
from app.api.v1.endpoints import sterling_v2 as v2_endpoint


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_v2_health_and_config(client):
    r = client.get("/api/v1/sterling-v2/health")
    assert r.status_code == 200
    assert r.json()["engine"] == "sterling_v2"
    c = client.get("/api/v1/sterling-v2/config")
    assert c.status_code == 200
    assert c.json()["enabled"] is False
    assert c.json()["auto_execute"] is False


def test_v2_signals_shape_and_paper_only(client, monkeypatch):
    """Exercise the response contract without depending on optional local parquet data.

    CI does not ship the research dataset, so an assertion against the machine's data
    directory made this endpoint test alternate between one-or-more rows locally and an
    empty list in a clean runner. Patch the endpoint's data/research boundaries and keep
    the HTTP serialization path itself under test.
    """
    monkeypatch.setattr(
        v2_endpoint,
        "V2_SIGNALS_CONFIG",
        [("BTC", "4h", "ma_crossover", "Intraday")],
    )
    monkeypatch.setattr(v2_endpoint.D, "list_symbols", lambda: {"BTCUSD": "fixture.parquet"})
    monkeypatch.setattr(v2_endpoint, "_resampled", lambda _path, _tf: object())
    monkeypatch.setattr(
        v2_endpoint.R,
        "latest_v2_signal",
        lambda _data, strat: {"current_price": 101.0, "strategy": strat},
    )
    monkeypatch.setattr(
        v2_endpoint.I,
        "build_instrument_signals",
        lambda _sig, _strat, _profile: (
            [
                {
                    "instrument_type": "spot",
                    "side": 1,
                    "entry": 100.0,
                    "stop": 95.0,
                    "target": 110.0,
                    "regime_ok": True,
                    "conviction": 80.0,
                    "bar_time": "2026-07-21T10:00:00Z",
                }
            ],
            "spot",
        ),
    )

    r = client.get("/api/v1/sterling-v2/signals")
    assert r.status_code == 200
    body = r.json()
    assert body["paper_only"] is True and body["auto_execute"] is False
    assert len(body["signals"]) == 1
    for s in body["signals"]:
        assert set(s) >= {"symbol", "tf", "side", "entry", "stop", "target",
                          "regime_ok", "conviction"}
        assert s["side"] in (-1, 0, 1)
        assert s["entry"] > 0
        if s["side"] != 0:  # an actionable signal carries finite levels
            assert s["stop"] is not None and s["target"] is not None


def test_v2_backtest_returns_finite_metrics(client):
    r = client.get("/api/v1/sterling-v2/backtest")
    assert r.status_code == 200
    body = r.json()
    assert body["paper_only"] is True
    assert body["per_symbol"]  # at least one symbol
    for sym, m in body["per_symbol"].items():
        for key in ("win", "pf", "sharpe", "net", "max_dd", "trades"):
            assert key in m and math.isfinite(m[key])
    for key in ("net", "max_dd", "sharpe"):
        assert math.isfinite(body["portfolio"][key])
