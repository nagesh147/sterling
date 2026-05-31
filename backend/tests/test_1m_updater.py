"""The 1m store must stay fresh. 1m was excluded from RESOLUTIONS, so the hourly
updater never touched it and it silently froze. fetch_core_1m() is the dedicated
loop that keeps it current for the core symbols."""
from __future__ import annotations

import asyncio

import app.services.delta_candle_fetcher as f


def test_1m_in_res_secs_with_correct_period():
    # the missing RES_SECS['1m'] would have defaulted to 3600 → broken incremental
    assert f.RES_SECS["1m"] == 60


def test_1m_excluded_from_all_symbol_fetch():
    # 1m must NOT be in the all-symbol hourly list (would hammer 100+ products)
    assert "1m" not in f.RESOLUTIONS
    assert "BTCUSD" in f.CORE_SYMBOLS


def test_fetch_core_1m_fetches_1m_for_each_core_symbol(monkeypatch):
    calls = []

    async def fake_fetch(symbol, resolution, lookback_secs=None):
        calls.append((symbol, resolution, lookback_secs))
        return 7

    monkeypatch.setattr(f, "fetch_symbol_resolution", fake_fetch)
    monkeypatch.setattr(f, "CORE_SYMBOLS", ["BTCUSD", "ETHUSD"])
    summary = asyncio.run(f.fetch_core_1m())

    assert [c[0] for c in calls] == ["BTCUSD", "ETHUSD"]
    assert all(c[1] == "1m" for c in calls)                  # always 1m
    assert all(c[2] == f.ONE_MIN_LOOKBACK_SECS for c in calls)  # capped backfill
    assert summary == {"BTCUSD:1m": 7, "ETHUSD:1m": 7}


def test_fetch_core_1m_reentrancy_guard(monkeypatch):
    monkeypatch.setattr(f, "_is_fetching_1m", True)
    out = asyncio.run(f.fetch_core_1m())
    assert out == {"status": "already_running"}


def test_one_failure_does_not_abort_the_rest(monkeypatch):
    async def fake_fetch(symbol, resolution, lookback_secs=None):
        if symbol == "BTCUSD":
            raise RuntimeError("api down")
        return 3

    monkeypatch.setattr(f, "fetch_symbol_resolution", fake_fetch)
    monkeypatch.setattr(f, "CORE_SYMBOLS", ["BTCUSD", "ETHUSD"])
    summary = asyncio.run(f.fetch_core_1m())
    assert summary["BTCUSD:1m"] == -1      # logged, marked, not raised
    assert summary["ETHUSD:1m"] == 3        # the rest still ran
