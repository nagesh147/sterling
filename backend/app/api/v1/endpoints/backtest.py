from fastapi import APIRouter, HTTPException, Request
from app.schemas.backtest import BacktestRequest, BacktestResult
from app.services.exchanges import instrument_registry as registry
from app.engines.backtest.backtest_engine import run_backtest

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestResult)
async def run_backtest_endpoint(
    body: BacktestRequest,
    request: Request,
) -> BacktestResult:
    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    adapter = request.app.state.adapter

    # Fetch enough historical candles for the lookback window
    limit_1h = min(body.lookback_days * 24, 720)  # cap at 720 bars (~30 days)
    limit_4h = min(body.lookback_days * 6 + 60, 300)  # extra buffer for EMA50 warmup

    try:
        candles_4h = await adapter.get_candles(inst, "4H", limit=limit_4h)
        candles_1h = await adapter.get_candles(inst, "1H", limit=limit_1h)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}")

    return run_backtest(
        underlying=sym,
        candles_4h=candles_4h,
        candles_1h=candles_1h,
        lookback_days=body.lookback_days,
        sample_every_n_bars=body.sample_every_n_bars,
    )
