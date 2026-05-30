"""Edge feed integration into _collect_armed_signals.

Verifies the edge branch pulls registry combos, runs the generator against the
OHLCV store, and tags signals so the candidate layer can label them — without
needing a live exchange adapter.
"""
from __future__ import annotations

import types

import pytest

from app.api.v1.endpoints import derivatives as D
from app.engines.edge.registry import EdgeCombo, EdgeRegistry


def _registry():
    combo = EdgeCombo(
        symbol="BTCUSD", tf="4h", strategy="breakout", profile="Intraday",
        trades=100, win_rate=0.42, pf=1.20, sharpe=1.31, expectancy=0.003,
        net_return=0.277, pnl_usd=138.0, max_dd=-0.28, signal_score=82.0,
    )
    return EdgeRegistry(combos={combo.key: combo})


def _breakout_rows():
    rows = []
    for i in range(44):
        base = 100.0 + (0.5 if i % 2 else -0.5)
        rows.append({"time": i * 14400, "open": base, "high": base + 1.0,
                     "low": base - 1.0, "close": base, "volume": 1000.0})
    rows.append({"time": 44 * 14400, "open": 100.0, "high": 116.0,
                 "low": 99.0, "close": 115.0, "volume": 1000.0})
    return rows


def test_edge_candle_fetcher_wraps_store(monkeypatch):
    captured = {}

    def fake_get_candles(symbol, resolution, limit=500, since=None):
        captured["args"] = (symbol, resolution, limit)
        return _breakout_rows()

    monkeypatch.setattr("app.services.ohlcv_store.get_candles", fake_get_candles)
    candles = D._edge_candle_fetcher("BTCUSD", "4h", 320)
    assert captured["args"][0] == "BTCUSD"
    assert captured["args"][1] == "4h"
    assert len(candles) == 45
    # wrapped into Candle-like objects with ms timestamp + ohlc attributes
    assert candles[-1].close == 115.0
    assert candles[-1].timestamp_ms == 44 * 14400 * 1000


def test_collect_edge_branch_emits_tagged_signal(monkeypatch):
    monkeypatch.setattr(D, "_edge_registry", lambda app: _registry())
    monkeypatch.setattr("app.services.ohlcv_store.get_candles",
                        lambda *a, **k: _breakout_rows())

    out = D._collect_edge_signals(strategy_filter=None, underlying_filter=None,
                                  app=types.SimpleNamespace())
    assert len(out) == 1
    sid, sig = out[0]
    assert sig.strategy == "edge/breakout"
    assert sig.presized is True
    assert D._signal_source(sig.strategy) == "edge"


def test_collect_edge_respects_underlying_filter(monkeypatch):
    monkeypatch.setattr(D, "_edge_registry", lambda app: _registry())
    monkeypatch.setattr("app.services.ohlcv_store.get_candles",
                        lambda *a, **k: _breakout_rows())
    out = D._collect_edge_signals(strategy_filter=None, underlying_filter="ETHUSD",
                                  app=types.SimpleNamespace())
    assert out == []
