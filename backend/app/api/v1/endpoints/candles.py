import time
from typing import List
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/candles", tags=["candles"])

_VALID_TFS = {"1m", "5m", "15m", "1H", "4H", "D"}
_TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1H": 3600, "4H": 14400, "D": 86400}
_cache: dict = {}
_CACHE_TTL = 60


@router.get("/{underlying}")
async def get_candles(
    underlying: str,
    request: Request,
    tf: str = Query(default="15m"),
    limit: int = Query(default=300, ge=1, le=500),
) -> List[dict]:
    if tf not in _VALID_TFS:
        raise HTTPException(status_code=400, detail=f"Invalid tf: {tf!r}. Valid: {sorted(_VALID_TFS)}")

    sym = underlying.upper()
    cache_key = (sym, tf, limit)
    now = time.time()

    # Return cached completed bars (skip cache for last bar freshness)
    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    from app.services import adapter_manager as _adm
    from app.services.exchanges import instrument_registry as registry

    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    adapter = _adm.get_adapter() or getattr(request.app.state, "adapter", None)
    if not adapter:
        raise HTTPException(status_code=503, detail="No market data adapter available")

    try:
        candles = await adapter.get_candles(inst, tf, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}")

    result = [
        {
            "time": c.timestamp_ms // 1000,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in candles
    ]

    _cache[cache_key] = (now, result)
    return result
