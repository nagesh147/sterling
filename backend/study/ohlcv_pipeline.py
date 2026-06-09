"""Multi-symbol OHLCV data pipeline — the breadth unlock for the regime book.

Fetches liquid-coin OHLCV history from Binance's public REST klines endpoint
(no API key), normalises it to the 6-column unix-second schema the study modules
expect, and writes one parquet per symbol into a dedicated universe dir. A wide
basket is the only honest path to a deflation-provable (DSR ≥ 0.5) edge — see
docs/regime_book_before_after.md.

Stdlib-only network (urllib + json) so there is no new dependency. The live
fetch is impure; the transforms (`klines_to_frame`) and IO (`write_symbol_frame`
/ `load_universe`) are pure and unit-tested.

Run:  cd backend && .venv/bin/python -m study.ohlcv_pipeline --interval 4h
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time
import urllib.error
import urllib.request

import pandas as pd

from app.engines.edge.strategies import resample

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
DATA_DIR = "data/ohlcv"

# Curated liquid coins with usable history in the 2023-12 → present window.
# Stored as {COIN}USD (internal convention); fetched from Binance as {COIN}USDT.
UNIVERSE = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX",
    "LINK", "DOT", "LTC", "BCH", "ATOM", "UNI", "ETC", "XLM",
    "FIL", "APT", "ARB", "OP", "NEAR", "INJ", "AAVE", "SUI",
]

_INTERVAL_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "1d": 86_400_000,
}

_COLS = ["time", "open", "high", "low", "close", "volume"]


def _http_get_json(url: str, retries: int = 4, pause: float = 0.5):
    """GET JSON with linear backoff. Raises after `retries` failures."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sterling-study/1"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last = e
            time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {url} ({last})")


def fetch_klines(symbol: str, interval: str, start_ms: int | None = None,
                 end_ms: int | None = None, limit: int = 1000) -> list:
    """One Binance klines request (≤1000 rows). Returns raw kline rows."""
    url = f"{BINANCE_KLINES}?symbol={symbol}&interval={interval}&limit={limit}"
    if start_ms is not None:
        url += f"&startTime={int(start_ms)}"
    if end_ms is not None:
        url += f"&endTime={int(end_ms)}"
    return _http_get_json(url)


def fetch_history(symbol: str, interval: str, start_ms: int,
                  end_ms: int | None = None, pause: float = 0.25) -> list:
    """Paginate forward from start_ms to now (or end_ms), stitching ≤1000-row
    pages into the full raw kline history."""
    step = _INTERVAL_MS[interval]
    end_ms = end_ms or int(time.time() * 1000)
    out: list = []
    cursor = int(start_ms)
    while cursor < end_ms:
        page = fetch_klines(symbol, interval, start_ms=cursor, end_ms=end_ms, limit=1000)
        if not page:
            break
        out.extend(page)
        last_open = page[-1][0]
        nxt = last_open + step
        if nxt <= cursor:                     # no forward progress → stop
            break
        cursor = nxt
        if len(page) < 1000:                  # last page
            break
        time.sleep(pause)
    return out


def klines_to_frame(raw: list) -> pd.DataFrame:
    """Normalise raw Binance klines → [time(unix s, int), open, high, low,
    close, volume(float)], sorted by time and de-duplicated on time."""
    if not raw:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in _COLS}) \
            .astype({"time": "int64"})
    df = pd.DataFrame(raw).iloc[:, :6]
    df.columns = ["open_ms", "open", "high", "low", "close", "volume"]
    df["time"] = (df["open_ms"].astype("int64") // 1000).astype("int64")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype("float64")
    df = df[_COLS].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return df


def write_symbol_frame(df: pd.DataFrame, symbol: str, data_dir: str = DATA_DIR) -> str:
    """Write a 6-col frame to {data_dir}/{symbol}.parquet. Returns the path."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"{symbol}.parquet")
    df.to_parquet(path, index=False)
    return path


def download_symbol(coin: str, interval: str, start_ms: int,
                    data_dir: str = DATA_DIR) -> dict:
    """Fetch full history for one coin and persist it. Returns a coverage dict."""
    symbol = f"{coin}USD"
    raw = fetch_history(f"{coin}USDT", interval, start_ms)
    df = klines_to_frame(raw)
    path = write_symbol_frame(df, symbol, data_dir)
    span = (None, None)
    if len(df):
        span = (pd.to_datetime(df["time"].iloc[0], unit="s").date().isoformat(),
                pd.to_datetime(df["time"].iloc[-1], unit="s").date().isoformat())
    return {"symbol": symbol, "rows": len(df), "start": span[0], "end": span[1],
            "path": path}


def load_universe(tf: str, data_dir: str = DATA_DIR) -> dict:
    """Load every {data_dir}/*.parquet → resampled OHLCV+ATR frames, keyed by
    symbol. Drop-in for the regime book's per-symbol frames."""
    frames = {}
    for f in sorted(glob.glob(os.path.join(data_dir, "*.parquet"))):
        sym = os.path.basename(f)[:-len(".parquet")]
        d = pd.read_parquet(f, columns=_COLS)
        d["time"] = pd.to_datetime(d["time"], unit="s")
        d = d.set_index("time").sort_index()
        frames[sym] = resample(d, tf)
    return frames


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download a multi-symbol OHLCV universe.")
    ap.add_argument("--interval", default="4h", choices=list(_INTERVAL_MS))
    ap.add_argument("--start", default="2023-12-29", help="YYYY-MM-DD history start")
    ap.add_argument("--data-dir", default=DATA_DIR)
    ap.add_argument("--coins", nargs="*", default=UNIVERSE)
    args = ap.parse_args(argv)

    start_ms = int(pd.Timestamp(args.start, tz="UTC").timestamp() * 1000)
    print(f"Downloading {len(args.coins)} coins · {args.interval} · from {args.start}"
          f" → {args.data_dir}\n")
    print(f"{'symbol':>9} {'rows':>7}  {'start':>10}  {'end':>10}")
    ok = 0
    for coin in args.coins:
        try:
            r = download_symbol(coin, args.interval, start_ms, args.data_dir)
            print(f"{r['symbol']:>9} {r['rows']:>7}  {str(r['start']):>10}  {str(r['end']):>10}")
            ok += 1
        except Exception as e:                # one bad symbol must not abort the run
            print(f"{coin+'USD':>9} {'FAIL':>7}  {e}")
    print(f"\n{ok}/{len(args.coins)} symbols written to {args.data_dir}/")


if __name__ == "__main__":
    main()
