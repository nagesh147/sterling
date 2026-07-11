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
    limit: int = Query(default=1825, ge=1, le=1825),
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

    adapter = _adm.get_adapter() or getattr(request.app.state, "adapter", None)
    if not adapter:
        raise HTTPException(status_code=503, detail="No market data adapter available")

    inst = registry.get_instrument(sym)
    
    force_kite = False
    if inst and getattr(inst, "exchange", "") == "zerodha":
        force_kite = True
    elif sym.startswith("NSE:") or sym.startswith("BSE:") or sym.startswith("NFO:") or sym.startswith("MCX:"):
        force_kite = True
    
    # 1. Try matching against explicit Zerodha index symbols (e.g. NSE:NIFTY 50)
    if not inst:
        for candidate in registry.list_instruments():
            if getattr(candidate, "zerodha_index_symbol", None) == sym:
                inst = candidate
                force_kite = True
                break

    if force_kite:
        from app.services.exchanges.kite.accounts import _accounts, bootstrap as _bootstrap_kite, build_client as _build_kite
        _bootstrap_kite()
        active_kite = None
        for a in _accounts.values():
            if a.is_active and a.user_id == "default":
                active_kite = a
                break
        if not active_kite:
            for a in _accounts.values():
                if a.is_active:
                    active_kite = a
                    break
        if active_kite:
            adapter = _build_kite(active_kite)
        else:
            raise HTTPException(status_code=503, detail="No active Kite account available for Zerodha historical data")

    # 2. Fallback for arbitrary ad-hoc symbols (e.g. NSE:RELIANCE)
    if not inst and hasattr(adapter, "resolve_token"):
        exchange = "NSE"
        tradingsymbol = sym
        if ":" in sym:
            exchange, tradingsymbol = sym.split(":", 1)
        
        try:
            token = await adapter.resolve_token(tradingsymbol, exchange)
            if token:
                from app.schemas.instruments import InstrumentMeta
                inst = InstrumentMeta(
                    underlying=tradingsymbol,
                    quote_currency="INR",
                    contract_multiplier=1.0,
                    tick_size=0.05,
                    strike_step=0.0,
                    has_options=False,
                    exchange=exchange.lower(),
                    exchange_currency="INR",
                    perp_symbol="",
                    index_name=tradingsymbol,
                    dvol_symbol=None,
                    zerodha_token=token,
                    zerodha_index_symbol=sym,
                    description=f"Ad-hoc instrument {sym}"
                )
        except Exception:
            pass

    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    try:
        candles = await adapter.get_candles(inst, tf, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}") from exc

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
