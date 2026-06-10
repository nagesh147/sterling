"""Equity-index data pipeline — the UNCORRELATED-market unlock for the regime book.

Crypto-coin breadth failed (the coins are ~0.8 correlated, so more of them adds
trade count but not independent information). The honest path to a
deflation-provable (DSR ≥ 0.5) edge is a market whose returns are independent of
crypto. Indian equity indices (NIFTY, BANKNIFTY) are exactly that.

Fetches daily OHLCV from Yahoo Finance's public chart endpoint (no API key,
stdlib urllib + json — no new dependency), normalises to the same 6-column
unix-second schema the study modules expect, and writes one parquet per symbol so
the EXACT `study.regime_book` machinery runs on it unchanged.

Yahoo tickers: NIFTY=^NSEI, BANKNIFTY=^NSEBANK (also works for ^GSPC, GC=F, etc.).
The live fetch is impure; the transform (`yahoo_to_frame`) and IO are pure + tested.

Run:  cd backend && .venv/bin/python -m study.equity_pipeline
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/"
EQUITY_DIR = "data/equity"
_COLS = ["time", "open", "high", "low", "close", "volume"]

# name -> Yahoo symbol. Indices are uncorrelated to crypto (the whole point).
SYMBOLS = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}


def _http_get_json(url: str, retries: int = 4, pause: float = 0.5):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last = e
            time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {url} ({last})")


def fetch_chart(yahoo_symbol: str, years: int = 10, interval: str = "1d") -> dict:
    """One Yahoo chart request for `years` of history at `interval`. Raw JSON."""
    p2 = int(time.time())
    p1 = p2 - 3600 * 24 * 365 * years
    sym = urllib.parse.quote(yahoo_symbol, safe="")        # ^NSEI -> %5ENSEI
    url = f"{YAHOO_CHART}{sym}?period1={p1}&period2={p2}&interval={interval}"
    return _http_get_json(url)


def yahoo_to_frame(raw: dict) -> pd.DataFrame:
    """Normalise a Yahoo chart payload → [time(unix s, int), open, high, low,
    close, volume(float)], dropping rows with any null OHLC, sorted + deduped."""
    try:
        res = raw["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError):
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in _COLS}) \
            .astype({"time": "int64"})
    df = pd.DataFrame({
        "time": ts, "open": q["open"], "high": q["high"],
        "low": q["low"], "close": q["close"], "volume": q["volume"],
    })
    df = df.dropna(subset=["open", "high", "low", "close"])
    df["time"] = df["time"].astype("int64")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype("float64")
    df["volume"] = df["volume"].fillna(0.0)
    return df[_COLS].drop_duplicates("time").sort_values("time").reset_index(drop=True)


def write_equity_frame(df: pd.DataFrame, name: str, data_dir: str = EQUITY_DIR) -> str:
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"{name}.parquet")
    df.to_parquet(path, index=False)
    return path


def download_symbol(name: str, yahoo_symbol: str, years: int, interval: str,
                    data_dir: str = EQUITY_DIR) -> dict:
    raw = fetch_chart(yahoo_symbol, years, interval)
    df = yahoo_to_frame(raw)
    path = write_equity_frame(df, name, data_dir)
    span = (None, None)
    if len(df):
        span = (pd.to_datetime(df["time"].iloc[0], unit="s").date().isoformat(),
                pd.to_datetime(df["time"].iloc[-1], unit="s").date().isoformat())
    return {"name": name, "rows": len(df), "start": span[0], "end": span[1], "path": path}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download equity-index history from Yahoo.")
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--data-dir", default=EQUITY_DIR)
    args = ap.parse_args(argv)
    print(f"Downloading {len(SYMBOLS)} indices · {args.interval} · {args.years}y"
          f" → {args.data_dir}\n")
    print(f"{'name':>10} {'rows':>6}  {'start':>10}  {'end':>10}")
    for name, ysym in SYMBOLS.items():
        try:
            r = download_symbol(name, ysym, args.years, args.interval, args.data_dir)
            print(f"{r['name']:>10} {r['rows']:>6}  {str(r['start']):>10}  {str(r['end']):>10}")
        except Exception as e:
            print(f"{name:>10} {'FAIL':>6}  {e}")


if __name__ == "__main__":
    main()
