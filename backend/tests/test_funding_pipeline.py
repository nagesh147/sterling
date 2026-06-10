"""Binance perp funding pipeline — funding rows → 2-col parquet → Series.

Pure transform + IO round-trip tested deterministically; the live network
fetch is gated behind STERLING_NET_TESTS=1 so the suite stays offline."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from study.funding_pipeline import (
    funding_to_frame, write_funding_frame, load_funding,
)


def _row(funding_time_ms, rate):
    return {"symbol": "BTCUSDT", "fundingTime": funding_time_ms,
            "fundingRate": f"{rate}", "markPrice": "60000.0"}


def test_funding_to_frame_normalises_schema():
    raw = [_row(1703836800000, 0.0001), _row(1703865600000, -0.00005)]
    df = funding_to_frame(raw)
    assert list(df.columns) == ["time", "funding_rate"]
    assert df["time"].iloc[0] == 1703836800           # ms → unix seconds
    assert df["funding_rate"].iloc[1] == pytest.approx(-0.00005)
    assert df["funding_rate"].dtype == np.float64
    assert df["time"].dtype.kind in ("i", "u")


def test_funding_to_frame_sorts_and_dedupes():
    raw = [_row(1703865600000, -0.00005), _row(1703836800000, 0.0001),
           _row(1703865600000, 9.9)]                   # dup time
    df = funding_to_frame(raw)
    assert len(df) == 2
    assert df["time"].is_monotonic_increasing
    assert df["time"].iloc[0] == 1703836800


def test_funding_to_frame_empty_is_empty_framed():
    df = funding_to_frame([])
    assert list(df.columns) == ["time", "funding_rate"]
    assert len(df) == 0


def test_write_and_load_funding_round_trip(tmp_path):
    raw = [_row(1703836800000 + i * 28800000, 0.0001 * (i % 3 - 1))
           for i in range(10)]
    write_funding_frame(funding_to_frame(raw), "BTC", str(tmp_path))
    s = load_funding("BTC", str(tmp_path))
    assert isinstance(s, pd.Series)
    assert isinstance(s.index, pd.DatetimeIndex)
    assert len(s) == 10
    assert s.name == "funding_rate"


def test_load_funding_missing_returns_none(tmp_path):
    assert load_funding("NOPE", str(tmp_path)) is None


@pytest.mark.skipif(os.environ.get("STERLING_NET_TESTS") != "1",
                    reason="network test (set STERLING_NET_TESTS=1)")
def test_fetch_funding_live_smoke():
    from study.funding_pipeline import fetch_funding_page
    raw = fetch_funding_page("BTCUSDT", limit=3)
    assert len(raw) >= 1
    assert "fundingRate" in raw[0] and "fundingTime" in raw[0]
