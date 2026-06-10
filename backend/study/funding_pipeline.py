"""Perpetual-funding history pipeline — the orthogonal-information source.

Funding measures crowd POSITIONING (who pays to hold the trade), not price, so it
is a candidate signal independent of the price-based sleeves that hit the
correlation wall (docs/regime_book_before_after.md). Fetches Binance USDⓈ-M perp
funding-rate history (no API key) from the public fapi endpoint, normalises it to
a 2-col unix-second schema, and writes one parquet per coin.

Stdlib-only network (urllib+json); transforms + IO are pure and unit-tested; the
live fetch is gated behind STERLING_NET_TESTS=1.

Run:  cd backend && .venv/bin/python -m study.funding_pipeline --coins BTC ETH SOL
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request

import pandas as pd

BINANCE_FUNDING = "https://fapi.binance.com/fapi/v1/fundingRate"
FUNDING_DIR = "data/funding"
FUNDING_INTERVAL_MS = 8 * 3_600_000          # Binance settles funding every 8h
_FCOLS = ["time", "funding_rate"]


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


def fetch_funding_page(symbol: str, start_ms: int | None = None,
                       end_ms: int | None = None, limit: int = 1000) -> list:
    """One Binance funding-rate request (≤1000 rows). Returns raw rows."""
    url = f"{BINANCE_FUNDING}?symbol={symbol}&limit={limit}"
    if start_ms is not None:
        url += f"&startTime={int(start_ms)}"
    if end_ms is not None:
        url += f"&endTime={int(end_ms)}"
    return _http_get_json(url)


def fetch_funding_history(symbol: str, start_ms: int, end_ms: int | None = None,
                          pause: float = 0.25) -> list:
    """Paginate forward from start_ms, stitching ≤1000-row pages into the full
    raw funding history."""
    end_ms = end_ms or int(time.time() * 1000)
    out: list = []
    cursor = int(start_ms)
    while cursor < end_ms:
        page = fetch_funding_page(symbol, start_ms=cursor, end_ms=end_ms, limit=1000)
        if not page:
            break
        out.extend(page)
        nxt = int(page[-1]["fundingTime"]) + FUNDING_INTERVAL_MS
        if nxt <= cursor:                     # no forward progress → stop
            break
        cursor = nxt
        if len(page) < 1000:                  # last page
            break
        time.sleep(pause)
    return out


def funding_to_frame(raw: list) -> pd.DataFrame:
    """Normalise raw Binance funding rows → [time(unix s, int), funding_rate
    (float)], sorted by time and de-duplicated on time."""
    if not raw:
        return pd.DataFrame({"time": pd.Series(dtype="int64"),
                             "funding_rate": pd.Series(dtype="float64")})
    df = pd.DataFrame(raw)
    df["time"] = (df["fundingTime"].astype("int64") // 1000).astype("int64")
    df["funding_rate"] = df["fundingRate"].astype("float64")
    df = df[_FCOLS].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return df


def write_funding_frame(df: pd.DataFrame, coin: str, data_dir: str = FUNDING_DIR) -> str:
    """Write a 2-col frame to {data_dir}/{coin}_funding.parquet. Returns the path."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"{coin}_funding.parquet")
    df.to_parquet(path, index=False)
    return path


def load_funding(coin: str, data_dir: str = FUNDING_DIR):
    """Load one coin's funding parquet → Series of funding_rate indexed by
    tz-naive UTC timestamp. Returns None if the file is missing."""
    path = os.path.join(data_dir, f"{coin}_funding.parquet")
    if not os.path.exists(path):
        return None
    d = pd.read_parquet(path, columns=_FCOLS)
    d["time"] = pd.to_datetime(d["time"], unit="s")
    return d.set_index("time")["funding_rate"].sort_index()


def download_funding(coin: str, start_ms: int, data_dir: str = FUNDING_DIR) -> dict:
    """Fetch full funding history for one coin and persist it. Coverage dict."""
    raw = fetch_funding_history(f"{coin}USDT", start_ms)
    df = funding_to_frame(raw)
    path = write_funding_frame(df, coin, data_dir)
    span = (None, None)
    if len(df):
        span = (pd.to_datetime(df["time"].iloc[0], unit="s").date().isoformat(),
                pd.to_datetime(df["time"].iloc[-1], unit="s").date().isoformat())
    return {"coin": coin, "rows": len(df), "start": span[0], "end": span[1],
            "path": path}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download Binance perp funding history.")
    ap.add_argument("--coins", nargs="*", default=["BTC", "ETH", "SOL"])
    ap.add_argument("--start", default="2023-12-29", help="YYYY-MM-DD history start")
    ap.add_argument("--data-dir", default=FUNDING_DIR)
    args = ap.parse_args(argv)

    start_ms = int(pd.Timestamp(args.start, tz="UTC").timestamp() * 1000)
    print(f"Downloading funding · {len(args.coins)} coins · from {args.start}"
          f" → {args.data_dir}\n")
    print(f"{'coin':>5} {'rows':>6}  {'start':>10}  {'end':>10}")
    for coin in args.coins:
        try:
            r = download_funding(coin, start_ms, args.data_dir)
            print(f"{r['coin']:>5} {r['rows']:>6}  {str(r['start']):>10}  {str(r['end']):>10}")
        except Exception as e:                # one bad coin must not abort the run
            print(f"{coin:>5} {'FAIL':>6}  {e}")


if __name__ == "__main__":
    main()
