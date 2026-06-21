"""Real Kite index-candle fetcher for the Sterling Kite Engine permutation sweep.

Pulls multi-year 1H candles for the four Kite index underlyings by stitching
together <=400-day windows (Kite caps a single 60minute historical request at
400 days). Caches each underlying to ``study/kite_cache/<token>_1H.npz`` so the
sweep re-runs offline without re-hitting the broker API.

Data is REAL (the live Zerodha historical API, read-only — no orders). Run once
with a valid Kite session; subsequent sweeps read the cache.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta

import numpy as np

from app.services import db
from app.services.exchanges.kite import accounts as ka
from app.services.exchanges.kite.client import _parse_kite_ts

CACHE_DIR = os.path.join(os.path.dirname(__file__), "kite_cache")

# The Kite index universe (no crypto). spot_token drives historical fetches.
INDICES = [
    {"name": "NIFTY 50",          "token": 256265, "option_name": "NIFTY",     "strike_step": 50.0},
    {"name": "NIFTY BANK",        "token": 260105, "option_name": "BANKNIFTY", "strike_step": 100.0},
    {"name": "NIFTY FIN SERVICE", "token": 257801, "option_name": "FINNIFTY",  "strike_step": 50.0},
    {"name": "SENSEX",            "token": 265,    "option_name": "SENSEX",    "strike_step": 100.0},
]

_WINDOW_DAYS = 380          # < Kite's 400-day single-request cap
_START = datetime(2019, 1, 1)   # index 1H history is plentiful from here


async def _stitch_history(client, token: int) -> dict:
    """Fetch 1H candles token-wide from _START to now by walking 380-day windows.
    Returns dict of parallel numpy arrays (ts_ms, o, h, l, c, v), de-duped+sorted."""
    now = datetime.now()
    rows: list = []
    cursor = _START
    while cursor < now:
        end = min(cursor + timedelta(days=_WINDOW_DAYS), now)
        frm = cursor.strftime("%Y-%m-%d %H:%M:%S")
        to = end.strftime("%Y-%m-%d %H:%M:%S")
        for attempt in range(4):
            try:
                data = await client.get_historical(token, "60minute", frm, to)
                rows.extend(data.get("candles", []))
                break
            except Exception as exc:  # noqa: BLE001
                wait = 0.75 * (2 ** attempt) if "429" in str(exc) else 0.5
                if attempt == 3:
                    print(f"    window {frm[:10]}..{to[:10]} failed: {exc}")
                else:
                    await asyncio.sleep(wait)
        cursor = end
        await asyncio.sleep(0.35)  # be gentle on the rate limiter

    # de-dup by timestamp, sort
    seen: dict = {}
    for r in rows:
        try:
            ts = _parse_kite_ts(str(r[0]))
            seen[ts] = (float(r[1]), float(r[2]), float(r[3]), float(r[4]),
                        float(r[5]) if len(r) > 5 else 0.0)
        except (IndexError, ValueError, TypeError):
            continue
    ts_sorted = sorted(seen)
    arr = np.array([seen[t] for t in ts_sorted], dtype=float)
    return {
        "ts": np.array(ts_sorted, dtype=np.int64),
        "o": arr[:, 0], "h": arr[:, 1], "l": arr[:, 2], "c": arr[:, 3], "v": arr[:, 4],
    }


def _cache_path(token: int) -> str:
    return os.path.join(CACHE_DIR, f"{token}_1H.npz")


def load_cached(token: int):
    p = _cache_path(token)
    if not os.path.exists(p):
        return None
    z = np.load(p)
    return {k: z[k] for k in z.files}


async def fetch_all(force: bool = False) -> dict:
    """Fetch (or load cached) candles for every index. Returns {name: arrays}."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    db.init()
    ka.bootstrap()
    accts = list(ka._accounts.values())
    if not accts:
        raise RuntimeError("No Kite account in DB — cannot fetch real data.")
    a = accts[0]
    if not a.connected:
        raise RuntimeError("Kite account has no access token — log in first.")
    client = await ka.acquire_client(a)
    out: dict = {}
    try:
        for idx in INDICES:
            cached = None if force else load_cached(idx["token"])
            if cached is not None and len(cached["c"]) > 100:
                out[idx["name"]] = cached
                d0 = datetime.utcfromtimestamp(int(cached["ts"][0]) / 1000).date()
                d1 = datetime.utcfromtimestamp(int(cached["ts"][-1]) / 1000).date()
                print(f"  [cache] {idx['name']:<18} {len(cached['c']):>5} bars  {d0}..{d1}")
                continue
            print(f"  [fetch] {idx['name']} (token {idx['token']}) ...")
            arrs = await _stitch_history(client, idx["token"])
            if len(arrs["c"]) <= 100:
                print(f"    only {len(arrs['c'])} bars — skipping {idx['name']}")
                continue
            np.savez_compressed(_cache_path(idx["token"]), **arrs)
            out[idx["name"]] = arrs
            d0 = datetime.utcfromtimestamp(int(arrs["ts"][0]) / 1000).date()
            d1 = datetime.utcfromtimestamp(int(arrs["ts"][-1]) / 1000).date()
            print(f"    saved {len(arrs['c'])} bars  {d0}..{d1}")
    finally:
        await client.close()
    return out


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    res = asyncio.run(fetch_all(force="--force" in os.sys.argv))
    print(f"\nFetched {len(res)} underlyings.")
