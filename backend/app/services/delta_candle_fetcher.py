"""
Delta Exchange India OHLCV fetcher.
Fetches historical candles and stores them incrementally — never re-fetches
what's already stored. Designed to run once at startup and then on a
background schedule to keep data fresh.
"""
import asyncio
import time
from typing import Dict, List, Optional

import httpx

from app.core.logging import get_logger
from app.services import ohlcv_store

log = get_logger(__name__)

DELTA_CANDLE_URL = "https://api.india.delta.exchange/v2/history/candles"
MAX_PER_REQUEST = 2000       # Delta Exchange cap
REQUEST_DELAY   = 0.35       # seconds between requests (avoid 429)
LOOKBACK_SECS   = 180 * 86_400  # 6 months

SYMBOLS     = ["BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD"]
RESOLUTIONS = ["5m", "15m", "30m", "1h", "2h", "4h"]

RES_SECS: Dict[str, int] = {
    "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400,
}

_is_fetching = False
_last_run_summary: Dict[str, int] = {}


async def _fetch_chunk(
    client: httpx.AsyncClient,
    symbol: str,
    resolution: str,
    start: int,
    end: int,
) -> List[Dict]:
    """One HTTP request to Delta Exchange. Returns raw candle dicts."""
    for attempt in range(2):
        try:
            resp = await client.get(
                DELTA_CANDLE_URL,
                params={
                    "symbol": symbol,
                    "resolution": resolution,
                    "start": start,
                    "end": end,
                },
                timeout=20,
            )
            if resp.status_code == 429:
                log.warning("OHLCV rate-limited — sleeping 3s")
                await asyncio.sleep(3)
                continue
            if resp.status_code == 404:
                return []  # symbol not available on this exchange
            resp.raise_for_status()
            data = resp.json()
            return data.get("result") or []
        except httpx.TimeoutException:
            if attempt == 0:
                await asyncio.sleep(1)
            else:
                log.warning("OHLCV timeout: %s/%s [%d-%d]", symbol, resolution, start, end)
        except Exception as exc:
            if attempt == 0:
                await asyncio.sleep(1)
            else:
                log.warning("OHLCV error: %s/%s: %s", symbol, resolution, exc)
    return []


async def fetch_symbol_resolution(symbol: str, resolution: str) -> int:
    """
    Fetch all missing candles for (symbol, resolution).
    Starts from the latest stored candle (or 6 months ago) and walks to now.
    Returns total candles fetched.
    """
    res_secs   = RES_SECS.get(resolution, 3600)
    chunk_secs = MAX_PER_REQUEST * res_secs
    now        = int(time.time())

    latest = ohlcv_store.get_latest_time(symbol, resolution)
    if latest:
        start = latest + res_secs   # one candle after the newest stored
    else:
        start = now - LOOKBACK_SECS

    if start >= now - res_secs:
        return 0  # up to date

    total   = 0
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient(headers=headers) as client:
        cursor = start
        while cursor < now:
            end     = min(cursor + chunk_secs, now)
            candles = await _fetch_chunk(client, symbol, resolution, cursor, end)
            if not candles:
                break
            ohlcv_store.upsert_candles(symbol, resolution, candles)
            total  += len(candles)
            cursor  = end + res_secs
            if len(candles) < MAX_PER_REQUEST:
                break  # no more history
            await asyncio.sleep(REQUEST_DELAY)

    return total


async def run_full_fetch(symbols: Optional[List[str]] = None) -> Dict[str, int]:
    """
    Fetch/update all symbols × resolutions.
    Skips pairs that are already up to date.
    Safe to call concurrently — second call returns immediately.
    """
    global _is_fetching, _last_run_summary
    if _is_fetching:
        return {"status": "already_running"}

    _is_fetching = True
    summary: Dict[str, int] = {}
    target_syms = symbols or SYMBOLS

    try:
        for sym in target_syms:
            for res in RESOLUTIONS:
                try:
                    added = await fetch_symbol_resolution(sym, res)
                    key   = f"{sym}:{res}"
                    summary[key] = added
                    if added > 0:
                        log.info("OHLCV fetched %s/%s: +%d candles", sym, res, added)
                        await asyncio.sleep(REQUEST_DELAY)
                except Exception as exc:
                    log.warning("OHLCV fetch error %s/%s: %s", sym, res, exc)
                    summary[f"{sym}:{res}"] = -1
    finally:
        _is_fetching = False
        _last_run_summary = summary

    total = sum(v for v in summary.values() if v > 0)
    log.info("OHLCV full fetch complete — %d new candles across %d pairs", total, len(summary))
    return summary


def is_fetching() -> bool:
    return _is_fetching


def last_summary() -> Dict[str, int]:
    return _last_run_summary.copy()
