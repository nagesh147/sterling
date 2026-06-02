"""Data loader for the derivatives edge study.

Loads vector_store_1m parquet files, resamples to target timeframes,
and recomputes ATR(14). Memory-safe: loads one symbol at a time and
gc.collect()'s between them (matching robustness_scan.py pattern).
"""
from __future__ import annotations

import gc
import glob
import logging
import os

import pandas as pd

from app.engines.edge.strategies import resample

log = logging.getLogger(__name__)

# Columns actually needed downstream — everything else is dropped.
_REQUIRED_COLS = ["time", "open", "high", "low", "close", "volume"]


def load_parquet(symbol: str, base_dir: str = ".") -> pd.DataFrame | None:
    """Load the 1m parquet for `symbol` (e.g. 'BTCUSD'), set time index.

    Returns None if the file is missing or unreadable (caller skips).
    """
    path = os.path.join(base_dir, f"vector_store_1m_{symbol}.parquet")
    if not os.path.exists(path):
        log.warning("No parquet for %s (expected at %s)", symbol, path)
        return None
    try:
        df = pd.read_parquet(path, columns=_REQUIRED_COLS)
    except ValueError:
        # File might have different columns — try all columns then subset.
        df = pd.read_parquet(path)
        missing = set(_REQUIRED_COLS) - set(df.columns)
        if missing:
            log.warning("%s missing columns: %s", symbol, sorted(missing))
        df = df[[c for c in _REQUIRED_COLS if c in df.columns]].copy()
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], unit="s")
    else:
        # If index is already datetime, reset and rename
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={"index": "time"}, inplace=True)
    df = df.set_index("time").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    if df.empty:
        log.warning("Empty dataframe for %s", symbol)
        return None
    return df


def prepare_data(
    symbols: list[str],
    timeframes: list[tuple[str, str]],   # [("15min", "15m"), ...]
    base_dir: str = ".",
) -> dict[tuple[str, str], pd.DataFrame]:
    """Resample 1m data to each target TF for each symbol.

    Returns {(symbol, tf_label): resampled_df} dict. Symbols with
    missing/malformed data are silently skipped.
    """
    cache: dict[tuple[str, str], pd.DataFrame] = {}
    for sym in symbols:
        df1 = load_parquet(sym, base_dir)
        if df1 is None:
            continue
        for rule, tf in timeframes:
            try:
                dft = resample(df1, rule)
            except Exception:
                log.exception("Resample failed for %s @ %s", sym, rule)
                continue
            if dft.empty:
                log.warning("Empty resampled df for %s @ %s", sym, rule)
                continue
            cache[(sym, tf)] = dft
        del df1
        gc.collect()
    log.info("Data cache ready: %d (symbol, tf) pairs loaded", len(cache))
    return cache
