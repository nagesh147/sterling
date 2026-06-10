"""Equity-index pipeline — Yahoo chart payload → 6-col parquet → universe frame.

Pure transform + IO round-trip tested deterministically; the live network fetch
is gated behind STERLING_NET_TESTS=1 so the suite stays offline."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from study.equity_pipeline import yahoo_to_frame, write_equity_frame


def _payload(times, opens, highs, lows, closes, vols):
    return {"chart": {"result": [{
        "timestamp": times,
        "indicators": {"quote": [{
            "open": opens, "high": highs, "low": lows,
            "close": closes, "volume": vols,
        }]},
    }]}}


def test_yahoo_to_frame_normalises_schema():
    raw = _payload([1528761600, 1528848000], [10800, 10850], [10900, 10950],
                   [10750, 10800], [10880, 10920], [0, 0])
    df = yahoo_to_frame(raw)
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert df["time"].iloc[0] == 1528761600
    assert df["close"].iloc[1] == pytest.approx(10920.0)
    assert df["time"].dtype.kind in ("i", "u")
    assert df["open"].dtype == np.float64


def test_yahoo_to_frame_drops_null_rows():
    # Yahoo returns null OHLC on holidays/halts — those rows must be dropped.
    raw = _payload([1, 2, 3], [10, None, 12], [11, None, 13],
                   [9, None, 11], [10, None, 12], [100, None, 120])
    df = yahoo_to_frame(raw)
    assert len(df) == 2
    assert list(df["time"]) == [1, 3]


def test_yahoo_to_frame_empty_payload_is_empty_framed():
    df = yahoo_to_frame({"chart": {"result": []}})
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert len(df) == 0


def test_write_and_load_universe_round_trip(tmp_path):
    from study.ohlcv_pipeline import load_universe
    t0 = 1528761600
    rows = {"time": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
    for i in range(300):
        px = 10000 * (1 + 0.001 * i)
        rows["time"].append(t0 + i * 86400)
        rows["open"].append(px); rows["high"].append(px * 1.01)
        rows["low"].append(px * 0.99); rows["close"].append(px * 1.002)
        rows["volume"].append(0.0)
    write_equity_frame(pd.DataFrame(rows), "NIFTY", str(tmp_path))
    frames = load_universe("1d", data_dir=str(tmp_path))
    assert "NIFTY" in frames
    df = frames["NIFTY"]
    assert {"open", "high", "low", "close", "atr"} <= set(df.columns)
    assert df["atr"].notna().any()


@pytest.mark.skipif(os.environ.get("STERLING_NET_TESTS") != "1",
                    reason="network test (set STERLING_NET_TESTS=1)")
def test_fetch_chart_live_smoke():
    from study.equity_pipeline import fetch_chart
    raw = fetch_chart("^NSEI", years=1)
    assert raw["chart"]["result"][0]["timestamp"]
