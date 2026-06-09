"""Multi-symbol OHLCV pipeline — Binance klines → 6-col parquet → universe frames.

Pure transforms and the IO round-trip are tested deterministically; the live
network fetch is gated behind STERLING_NET_TESTS=1 so the suite stays offline."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from study.ohlcv_pipeline import (
    klines_to_frame, write_symbol_frame, load_universe,
)


def _raw(open_ms, o, h, l, c, v):
    # Binance kline row: openTime(ms), o,h,l,c,v, closeTime, quoteVol, trades, ...
    return [open_ms, f"{o}", f"{h}", f"{l}", f"{c}", f"{v}",
            open_ms + 999, "0", 1, "0", "0", "0"]


def test_klines_to_frame_normalises_schema():
    raw = [
        _raw(1703856000000, 42000, 42500, 41800, 42300, 123.4),
        _raw(1703859600000, 42300, 42900, 42250, 42800, 98.7),
    ]
    df = klines_to_frame(raw)
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert df["time"].iloc[0] == 1703856000          # ms → unix seconds
    assert df["close"].iloc[1] == pytest.approx(42800.0)
    assert df["open"].dtype == np.float64
    assert df["time"].dtype.kind in ("i", "u")        # integer seconds


def test_klines_to_frame_sorts_and_dedupes():
    raw = [
        _raw(1703859600000, 42300, 42900, 42250, 42800, 98.7),   # later first
        _raw(1703856000000, 42000, 42500, 41800, 42300, 123.4),  # earlier second
        _raw(1703859600000, 99999, 99999, 99999, 99999, 1),      # dup of row 1's time
    ]
    df = klines_to_frame(raw)
    assert len(df) == 2                               # dedup on time
    assert df["time"].is_monotonic_increasing         # sorted
    assert df["time"].iloc[0] == 1703856000


def test_klines_to_frame_empty_is_empty_framed():
    df = klines_to_frame([])
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert len(df) == 0


def test_write_and_load_universe_round_trip(tmp_path):
    # Two synthetic symbols, hourly bars → load_universe resamples to 4h + ATR.
    for sym, lvl in (("BTCUSD", 60000.0), ("ETHUSD", 3000.0)):
        t0 = 1703856000
        rows = []
        for i in range(200):
            px = lvl * (1 + 0.001 * i)
            rows.append(_raw((t0 + i * 3600) * 1000, px, px * 1.01, px * 0.99,
                             px * 1.002, 10.0))
        write_symbol_frame(klines_to_frame(rows), sym, str(tmp_path))

    frames = load_universe("4h", data_dir=str(tmp_path))
    assert set(frames) == {"BTCUSD", "ETHUSD"}
    for sym, df in frames.items():
        assert {"open", "high", "low", "close", "volume", "atr"} <= set(df.columns)
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df["atr"].notna().any()                # ATR computed on 4h bars


# --- production hardening: forming-bar guard + data integrity -----------
from study.ohlcv_pipeline import drop_forming_bar, validate_universe


def _hourly_frame(start, n, freq="4h"):
    idx = pd.date_range(start, periods=n, freq=freq)
    return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0,
                         "close": 1.0, "volume": 1.0, "atr": 0.1}, index=idx)


def test_drop_forming_bar_removes_unclosed_tail():
    # bars open 00,04,08,12; at 13:00 the 12:00 bar (closes 16:00) is forming.
    df = _hourly_frame("2026-06-09 00:00", 4)
    out = drop_forming_bar(df, "4h", now="2026-06-09 13:00")
    assert len(out) == 3
    assert out.index[-1] == pd.Timestamp("2026-06-09 08:00")   # last CLOSED bar


def test_drop_forming_bar_keeps_all_when_fully_closed():
    df = _hourly_frame("2026-06-09 00:00", 3)                  # 00,04,08
    out = drop_forming_bar(df, "4h", now="2026-06-09 13:00")   # 08 closed at 12:00
    assert len(out) == 3


def test_validate_universe_flags_stale_gappy_and_short():
    good = _hourly_frame("2026-06-01 00:00", 60)
    stale = _hourly_frame("2026-05-01 00:00", 60)             # last bar way old
    gappy = _hourly_frame("2026-06-01 00:00", 60)
    gappy = gappy.drop(gappy.index[20:25])                    # punch a gap
    frames = {"BTCUSD": good, "ETHUSD": stale, "SOLUSD": gappy}
    issues = validate_universe(frames, "4h", now="2026-06-10 12:00",
                               min_bars=50)
    joined = " ".join(issues)
    assert "ETHUSD" in joined and "stale" in joined
    assert "SOLUSD" in joined and "gap" in joined
    assert "BTCUSD" not in joined                              # the clean one passes


def test_validate_universe_flags_too_few_bars():
    frames = {"BTCUSD": _hourly_frame("2026-06-08 00:00", 5)}
    issues = validate_universe(frames, "4h", now="2026-06-09 04:00", min_bars=50)
    assert any("BTCUSD" in i and "bars" in i for i in issues)


@pytest.mark.skipif(os.environ.get("STERLING_NET_TESTS") != "1",
                    reason="network test (set STERLING_NET_TESTS=1)")
def test_fetch_klines_live_smoke():
    from study.ohlcv_pipeline import fetch_klines
    raw = fetch_klines("BTCUSDT", "4h", limit=3)
    assert len(raw) >= 1
    assert len(raw[0]) >= 6                            # a real kline row
