"""Daily SMA/EMA + RSI/ADX strategy API.

Self-contained surface for the strategy module:
  GET  /strategy/config           — current config
  POST /strategy/config           — update the live config (held in app.state)
  GET  /strategy/signals          — scan every servable instrument
  GET  /strategy/evaluate/{sym}   — live evaluation snapshot for the dashboard
  POST /strategy/backtest         — historical replay over `lookback_days`
  POST /strategy/execute          — route the live trade plan to paper/live

Execution delegates to the existing `/trading/place-order` path so all the
live-safety, idempotency and bracket logic is reused (no duplication).
"""
from __future__ import annotations

import asyncio
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request

from app.services.exchanges import instrument_registry as registry
from app.services import adapter_manager as _adm
from app.api.v1.endpoints.directional import _adapter_can_serve

from app.engines.triple_st.config import TripleSTConfig, default_config
from app.engines.triple_st import backtest as bt
from app.engines.triple_st.schemas import (
    StrategyEvaluation, ConfigResponse,
    BacktestRequest, TripleSTBacktestResult, ExecuteRequest, ExecuteResponse,
    SignalSummary, SignalScanResponse,
)

router = APIRouter(prefix="/strategy", tags=["strategy"])


# ─── config (held in app.state, falls back to defaults) ──────────────────────


def _get_config(request: Request) -> TripleSTConfig:
    cfg = getattr(request.app.state, "triple_st_config", None)
    if cfg is None:
        cfg = default_config()
        request.app.state.triple_st_config = cfg
    return cfg


@router.get("/config", response_model=ConfigResponse)
async def get_config(request: Request) -> ConfigResponse:
    return ConfigResponse(config=_get_config(request))


@router.post("/config", response_model=ConfigResponse)
async def set_config(body: TripleSTConfig, request: Request) -> ConfigResponse:
    request.app.state.triple_st_config = body
    return ConfigResponse(config=body)


# ─── candle fetch (daily) ────────────────────────────────────────────────────


def _daily_limit(cfg: TripleSTConfig) -> int:
    """Daily bars to fetch: SMA period + warm-up + a comfortable buffer."""
    return min(cfg.sma_period + cfg.warmup_bars + 80, 1000)


async def _fetch_daily(request: Request, sym: str, cfg: TripleSTConfig):
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(status_code=400, detail=f"{sym} not available on {src} data source")
    adapter = _adm.get_adapter() or request.app.state.adapter
    try:
        candles = await adapter.get_candles(inst, "1D", limit=_daily_limit(cfg))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}")
    return inst, candles


# ─── evaluate / scan ─────────────────────────────────────────────────────────


def _to_summary(ev: StrategyEvaluation) -> SignalSummary:
    p = ev.trade_plan
    return SignalSummary(
        underlying=ev.underlying, close=ev.close, direction=ev.direction,
        entry_ok=ev.entry_ok, executable=ev.executable,
        sma=ev.sma, ema=ev.ema, rsi=ev.rsi, adx=ev.adx,
        above_sma=ev.above_sma, above_ema=ev.above_ema, rsi_gt_adx=ev.rsi_gt_adx,
        entry=p.entry if p else None, stop_loss=p.stop_loss if p else None,
        r_distance=p.r_distance if p else None,
        risk_pct=p.risk_pct if p else None, leverage=p.leverage if p else None,
        notional_usd=p.notional_usd if p else None, size_units=p.size_units if p else None,
        reason=ev.reason, timestamp_ms=ev.timestamp_ms,
    )


@router.get("/signals", response_model=SignalScanResponse)
async def signals(request: Request, armed_only: bool = False) -> SignalScanResponse:
    """Scan EVERY servable instrument and return a compact signal per symbol."""
    cfg = _get_config(request)
    src = _adm.get_data_source()
    adapter = _adm.get_adapter() or request.app.state.adapter
    now_ms = int(time.time() * 1000)
    limit = _daily_limit(cfg)

    instruments = [i for i in registry.list_instruments() if _adapter_can_serve(i, src)]
    sem = asyncio.Semaphore(6)

    async def _one(inst) -> SignalSummary:
        sym = inst.underlying
        async with sem:
            try:
                candles = await adapter.get_candles(inst, "1D", limit=limit)
            except Exception as exc:
                return SignalSummary(
                    underlying=sym, close=0.0, direction="none", entry_ok=False,
                    reason="candle fetch failed", error=str(exc)[:80], timestamp_ms=now_ms,
                )
        ev = bt.evaluate_live(sym, candles, cfg)
        return _to_summary(ev)

    results: List[SignalSummary] = await asyncio.gather(*[_one(i) for i in instruments])

    # Armed first, then by symbol for a stable order.
    results.sort(key=lambda s: (s.entry_ok, s.underlying), reverse=True)
    if armed_only:
        results = [s for s in results if s.entry_ok]

    return SignalScanResponse(
        signals=results, count=len(results),
        armed_count=sum(1 for s in results if s.entry_ok), timestamp_ms=now_ms,
    )


@router.get("/evaluate/{underlying}", response_model=StrategyEvaluation)
async def evaluate(underlying: str, request: Request) -> StrategyEvaluation:
    sym = underlying.upper()
    cfg = _get_config(request)
    _inst, candles = await _fetch_daily(request, sym, cfg)
    return bt.evaluate_live(sym, candles, cfg)


# ─── backtest ────────────────────────────────────────────────────────────────


def _store_candles(sym: str, resolution: str, lookback_days: int):
    """Load candles from the local OHLCV store (years of history) as `Candle`s.

    The store holds intraday history (~2y of 1H); `run_backtest` resamples to
    daily. Store keys are `<SYM>USD` with lowercase resolutions, `time` in s.
    """
    from app.services import ohlcv_store
    from app.schemas.market import Candle

    per_day = {"1h": 24, "4h": 6}.get(resolution, 24)
    limit = min(lookback_days * per_day + 300, 40_000)
    since = int(time.time()) - lookback_days * 86_400
    rows = ohlcv_store.get_candles(f"{sym}USD", resolution, limit=limit, since=since)
    return [
        Candle(timestamp_ms=int(r["time"]) * 1000, open=r["open"], high=r["high"],
               low=r["low"], close=r["close"], volume=r["volume"])
        for r in rows
    ]


@router.post("/backtest", response_model=TripleSTBacktestResult)
async def backtest(body: BacktestRequest, request: Request) -> TripleSTBacktestResult:
    from app.core.rate_limit import check_backtest
    check_backtest(request)

    sym = body.underlying.upper()
    cfg = body.config or _get_config(request)

    # Prefer the local store (deep 1H history → resampled to daily). Fall back to
    # the adapter's native daily candles when the store has too little.
    candles = _store_candles(sym, "1h", body.lookback_days)
    if len(candles) < (cfg.warmup_bars + 5) * 24:
        try:
            _inst, candles = await _fetch_daily(request, sym, cfg)
        except HTTPException:
            pass

    return bt.run_backtest(sym, candles, cfg, body.lookback_days)


# ─── execute (route live trade plan through the existing order path) ─────────


@router.post("/execute", response_model=ExecuteResponse)
async def execute(body: ExecuteRequest, request: Request) -> ExecuteResponse:
    sym = body.underlying.upper()
    cfg = _get_config(request)
    _inst, candles = await _fetch_daily(request, sym, cfg)
    ev = bt.evaluate_live(sym, candles, cfg)

    now_ms = int(time.time() * 1000)
    if ev.trade_plan is None:
        return ExecuteResponse(
            accepted=False, mode="paper", underlying=sym, direction=ev.direction,
            size_units=0.0, notional_usd=0.0, status="no_direction",
            reason=f"no directional setup: {ev.reason}", timestamp_ms=now_ms,
        )

    plan = ev.trade_plan
    # Size in integer contracts; reject sub-1-contract plans.
    contracts = max(0, int(round(plan.size_units)))
    if contracts < 1:
        return ExecuteResponse(
            accepted=False, mode="paper", underlying=sym, direction=plan.direction,
            size_units=plan.size_units, notional_usd=plan.notional_usd, status="size_too_small",
            reason="sized below 1 contract", timestamp_ms=now_ms,
        )

    # Delegate to the existing live/paper order path (reuses safety + brackets).
    # No fixed take-profit: the strategy exits on the RSI/ADX signal flip.
    from app.api.v1.endpoints.trading import LiveOrderRequest, place_live_order

    order = LiveOrderRequest(
        underlying=sym, direction=plan.direction, instrument_type="futures",
        size=float(contracts), leverage=plan.leverage, order_type="market",
        stop_loss=plan.stop_loss, take_profit=None,
        notes=f"[SMA/EMA·RSI/ADX] {plan.direction} "
              f"RSI={ev.rsi:.0f} ADX={ev.adx:.0f}",
    )
    resp = await place_live_order(order, request)

    return ExecuteResponse(
        accepted=resp.status not in ("rejected", "error"),
        mode=resp.mode, underlying=sym, direction=plan.direction,
        size_units=float(contracts), notional_usd=plan.notional_usd,
        entry_price=resp.entry_price, stop_loss=resp.stop_loss, take_profit=resp.take_profit,
        order_id=resp.order_id, paper_position_id=resp.paper_position_id,
        status=resp.status, reason=resp.message, timestamp_ms=resp.timestamp_ms or now_ms,
    )
