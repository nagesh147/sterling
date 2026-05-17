"""
OHLCV stored candle API — serves data from SQLite, updated by delta_candle_fetcher.
Provides status and manual trigger endpoints for the frontend.
"""
import time
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.services import ohlcv_store
from app.services.delta_candle_fetcher import (
    RESOLUTIONS, SYMBOLS, is_fetching, last_summary, run_full_fetch,
)

router = APIRouter(prefix="/ohlcv", tags=["ohlcv"])


@router.get("/status")
async def get_ohlcv_status():
    """Coverage summary + fetch state."""
    return {
        "is_fetching": is_fetching(),
        "last_summary": last_summary(),
        "coverage": ohlcv_store.get_status(),
        "supported_symbols": SYMBOLS,
        "supported_resolutions": RESOLUTIONS,
        "timestamp_ms": int(time.time() * 1000),
    }


@router.post("/fetch")
async def trigger_fetch(
    background_tasks: BackgroundTasks,
    symbol: Optional[str] = Query(default=None, description="Specific symbol, or all if omitted"),
):
    """Manually trigger a candle data fetch (runs in background)."""
    if is_fetching():
        return {"status": "already_running"}
    syms = [symbol.upper()] if symbol else None
    background_tasks.add_task(run_full_fetch, syms)
    return {"status": "started", "symbols": syms or SYMBOLS}


@router.get("")
async def get_candles(
    symbol: str = Query(default="BTCUSD"),
    resolution: str = Query(default="1h"),
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

    earliest = ohlcv_store.get_earliest_time(sym, resolution)
    latest   = ohlcv_store.get_latest_time(sym, resolution)

    return {
        "symbol": sym,
        "resolution": resolution,
        "count": len(candles),
        "earliest": earliest,
        "latest": latest,
        "is_fetching": is_fetching(),
        "candles": candles,
    }
