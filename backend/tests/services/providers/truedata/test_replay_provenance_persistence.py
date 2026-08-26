from __future__ import annotations

import pytest

from app.services.providers.truedata.bar_store import BarStore
from app.services.providers.truedata.tick_store import TickStore


def test_bar_store_persists_and_returns_provider_provenance(tmp_path) -> None:
    store = BarStore(tmp_path / "bars.sqlite")
    store.upsert(
        "NIFTY-I",
        [{"timestamp": "2026-08-17 09:15:00", "close": 24700, "source": "truedata", "source_version": "2.6"}],
        interval="1min",
        request_from="2026-08-17T09:15:00+05:30",
        request_to="2026-08-17T09:16:00+05:30",
    )
    row = store.load("NIFTY-I")[0]
    assert row["source"] == "truedata"
    assert row["source_version"] == "2.6"


def test_tick_store_persists_and_returns_provider_provenance(tmp_path) -> None:
    store = TickStore(tmp_path / "ticks.sqlite")
    store.upsert(
        "NIFTY-I",
        [{"timestamp": "2026-08-17 09:15:00", "ltp": 24700, "source": "truedata", "source_version": "2.6"}],
        request_from="2026-08-17T09:15:00+05:30",
        request_to="2026-08-17T09:16:00+05:30",
    )
    row = store.load("NIFTY-I")[0]
    assert row["source"] == "truedata"
    assert row["source_version"] == "2.6"


def test_bar_store_does_not_relabel_explicit_synthetic_row(tmp_path) -> None:
    store = BarStore(tmp_path / "bars.sqlite")
    store.upsert(
        "NIFTY-I",
        [{"timestamp": "2026-08-17 09:15:00", "close": 24700, "source": "synthetic", "source_version": "1.0"}],
        interval="1min",
        request_from="x",
        request_to="y",
    )
    row = store.load("NIFTY-I")[0]
    assert row["source"] == "synthetic"
    assert row["source_version"] == "1.0"


def test_tick_store_does_not_relabel_explicit_synthetic_row(tmp_path) -> None:
    store = TickStore(tmp_path / "ticks.sqlite")
    store.upsert(
        "NIFTY-I",
        [{"timestamp": "2026-08-17 09:15:00", "ltp": 24700, "source": "synthetic", "source_version": "1.0"}],
        request_from="x",
        request_to="y",
    )
    row = store.load("NIFTY-I")[0]
    assert row["source"] == "synthetic"
    assert row["source_version"] == "1.0"
