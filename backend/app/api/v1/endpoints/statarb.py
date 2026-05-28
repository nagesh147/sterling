"""Statistical Arbitrage endpoint.

Provides the configuration and live scan results for 3D Spreads / Co-integrated pairs.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.engines.statarb import StatArbConfig, default_statarb_config
from app.engines.statarb import StatArbScanResponse, scan_statarb_universe
from app.services import ohlcv_store
from app.services.db import get_config as _gc, set_config as _sc
from app.schemas.market import Candle

def _store_candles(sym: str, resolution: str, lookback_days: int):
    import time
    now_sec = int(time.time())
    since = now_sec - (lookback_days * 24 * 60 * 60)
    rows = ohlcv_store.get_candles(sym, resolution, limit=5000, since=since)
    if not rows:
        return []
    candles = [Candle(
        timestamp_ms=int(r["time"]) * 1000, 
        open=r["open"], 
        high=r["high"], 
        low=r["low"], 
        close=r["close"],
        volume=r["volume"], 
        is_closed=True
    ) for r in rows]
    
    # Inject live price from L2 Socket for real-time spread tracking
    from app.services.delta_l2_socket import l2_manager
    best_bid = l2_manager.best_bid.get(sym)
    best_ask = l2_manager.best_ask.get(sym)
    if best_bid and best_ask:
        mid_price = (best_bid[0] + best_ask[0]) / 2.0
        candles.append(Candle(
            timestamp_ms=int(time.time() * 1000),
            open=mid_price, high=mid_price, low=mid_price, close=mid_price,
            volume=0.0, is_closed=False
        ))
    
    return candles

router = APIRouter()

class StatArbConfigResponse(BaseModel):
    config: StatArbConfig

def _get_config(request: Request) -> StatArbConfig:
    cfg = getattr(request.app.state, "statarb_config", None)
    if cfg is None:
        saved = _gc("statarb_config")
        if saved:
            try:
                cfg = StatArbConfig.model_validate_json(saved)
            except Exception:
                cfg = default_statarb_config()
        else:
            cfg = default_statarb_config()
        request.app.state.statarb_config = cfg
    return cfg

@router.get("/config", response_model=StatArbConfigResponse)
async def get_config(request: Request) -> StatArbConfigResponse:
    return StatArbConfigResponse(config=_get_config(request))

@router.post("/config", response_model=StatArbConfigResponse)
async def set_config(body: StatArbConfig, request: Request) -> StatArbConfigResponse:
    request.app.state.statarb_config = body
    _sc("statarb_config", body.model_dump_json())
    return StatArbConfigResponse(config=body)

@router.get("/scan", response_model=StatArbScanResponse)
async def scan_market(request: Request) -> StatArbScanResponse:
    cfg = _get_config(request)
    if not cfg.enabled:
        return StatArbScanResponse(signals=[], count=0, armed_count=0, timestamp_ms=0)
        
    # We need to fetch candles for all unique assets defined in the pairs
    assets_to_fetch = set()
    for p in cfg.pairs:
        assets_to_fetch.add(p.asset_x)
        assets_to_fetch.add(p.asset_y)
        if p.asset_z:
            assets_to_fetch.add(p.asset_z)
            
    # Typically fetch enough bars for the lookback
    max_lookback_days = 30 # standard default
    
    # We need to structure a dictionary of resolutions to symbol -> list[Candle]
    # For now, we only support cfg.timeframe
    data_dict = {cfg.timeframe: {}}
    
    for symbol in assets_to_fetch:
        try:
            candles = _store_candles(symbol, cfg.timeframe, max_lookback_days)
            data_dict[cfg.timeframe][symbol] = candles
        except Exception:
            pass
            
    res = scan_statarb_universe(data_dict, cfg)
    return res
