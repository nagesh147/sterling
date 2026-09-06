"""
OHLCV stored candle API — serves candles from SQLite.

The store used to be filled by `delta_candle_fetcher`, whose universe was
["BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD"]. That fetcher went with the crypto
product surface, and with it the `POST /ohlcv/fetch` trigger it backed: there is
no equivalent "go fetch everything" for Kite, whose candles are hydrated on
demand by the replay runner instead. What remains is the read side.
"""
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from app.services import ohlcv_store

router = APIRouter(prefix="/ohlcv", tags=["ohlcv"])

#: Resolutions the store is written at. Previously imported from the crypto
#: fetcher; the replay runner writes 5m/15m/1m, and the rest are legacy reads.
RESOLUTIONS = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]


@router.get("/status")
async def get_ohlcv_status():
    """Coverage summary, straight from the store."""
    # `get_status()` is a GROUP BY over the whole table, so it stays off the
    # event loop.
    coverage = await run_in_threadpool(ohlcv_store.get_status)
    return {
        "coverage": coverage,
        "supported_symbols": sorted({row["symbol"] for row in coverage}),
        "supported_resolutions": RESOLUTIONS,
        "timestamp_ms": int(time.time() * 1000),
    }


@router.get("")
async def get_candles(
    symbol: str = Query(default="NIFTY"),
    resolution: str = Query(default="5m"),
    limit: int = Query(default=500, ge=10, le=5000),
    since: Optional[int] = Query(default=None, description="Unix timestamp (seconds) — return only candles after this"),
):
    """
    Return stored OHLCV candles.
    Results are in chronological order (oldest first).
    """
    sym = symbol.upper()
    if resolution not in RESOLUTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"resolution must be one of: {RESOLUTIONS}",
        )

    candles = ohlcv_store.get_candles(sym, resolution, limit=limit, since=since)

    return {
        "symbol": sym,
        "resolution": resolution,
        "count": len(candles),
        "earliest": ohlcv_store.get_earliest_time(sym, resolution),
        "latest": ohlcv_store.get_latest_time(sym, resolution),
        "candles": candles,
    }
