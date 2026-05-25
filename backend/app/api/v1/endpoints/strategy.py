"""Triple SuperTrend strategy API.

Self-contained surface for the new strategy module:
  GET  /strategy/config           — current config + mode/asset presets
  POST /strategy/config           — update the live config (held in app.state)
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

from app.engines.triple_st.config import (
    TripleSTConfig, MODE_TABLE, ASSET_TABLE, StrategyMode, AssetClass, default_config,
)
from app.engines.triple_st import backtest as bt
from app.engines.triple_st.schemas import (
    StrategyEvaluation, ConfigResponse, ModePresetView, AssetPresetView,
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


def _presets() -> ConfigResponse:
    modes = [
        ModePresetView(
            mode=m, min_confirm=p.min_confirm, risk_mult=p.risk_mult,
            be_trigger_r=p.be_trigger_r, trail_source=p.trail_source,
            partials=list(p.partials),
        )
        for m, p in MODE_TABLE.items()
    ]
    assets = [
        AssetPresetView(
            asset_class=a, sl_mult=p.sl_mult, tp_mult=p.tp_mult, min_adx=p.min_adx,
            squeeze_threshold=p.squeeze_threshold, short_modifier=p.short_modifier,
        )
        for a, p in ASSET_TABLE.items()
    ]
    return modes, assets


@router.get("/config", response_model=ConfigResponse)
async def get_config(request: Request) -> ConfigResponse:
    cfg = _get_config(request)
    modes, assets = _presets()
    return ConfigResponse(config=cfg, mode_presets=modes, asset_presets=assets)


@router.post("/config", response_model=ConfigResponse)
async def set_config(body: TripleSTConfig, request: Request) -> ConfigResponse:
    request.app.state.triple_st_config = body
    modes, assets = _presets()
    return ConfigResponse(config=body, mode_presets=modes, asset_presets=assets)


# ─── candle fetch helper (mirrors the directional endpoint conventions) ──────


async def _fetch_candles(request: Request, sym: str, lookback_days: int):
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(status_code=400, detail=f"{sym} not available on {src} data source")
    adapter = _adm.get_adapter() or request.app.state.adapter

    limit_1h = min(lookback_days * 24 + 150, 5000)
    limit_4h = min(lookback_days * 6 + 60, 1000)
    try:
        c1h = await adapter.get_candles(inst, "1H", limit=limit_1h)
        c4h = await adapter.get_candles(inst, "4H", limit=limit_4h)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}")

    # BTC reference (for the correlation / black-swan filters). Skip if sym is BTC.
    btc = None
    if sym != "BTC":
        binst = registry.get_instrument("BTC")
        if binst and _adapter_can_serve(binst, src):
            try:
                btc = await adapter.get_candles(binst, "1H", limit=limit_1h)
            except Exception:
                btc = None
    else:
        btc = c1h
    return inst, c1h, c4h, btc


# ─── evaluate ────────────────────────────────────────────────────────────────


def _to_summary(ev: StrategyEvaluation) -> SignalSummary:
    p = ev.trade_plan
    return SignalSummary(
        underlying=ev.underlying, close=ev.close, direction=ev.direction,
        entry_ok=ev.entry_ok, arrow=ev.arrow, consensus_count=ev.consensus_count,
        quality_total=ev.quality.total, quality_pass=ev.quality.passed,
        regime_label=ev.regime.label, effective_mode=ev.effective_mode,
        asset_class=ev.asset_class, executable=ev.executable,
        entry=p.entry if p else None, stop_loss=p.stop_loss if p else None,
        take_profit=p.take_profit if p else None, rr=p.rr if p else None,
        risk_pct=p.risk_pct if p else None, leverage=p.leverage if p else None,
        notional_usd=p.notional_usd if p else None, size_units=p.size_units if p else None,
        reason=ev.reason, timestamp_ms=ev.timestamp_ms,
    )


@router.get("/signals", response_model=SignalScanResponse)
async def signals(request: Request, armed_only: bool = False) -> SignalScanResponse:
    """Scan EVERY servable instrument and return a compact signal per symbol.

    Candle fetches run concurrently (bounded) and the BTC reference series is
    fetched once and shared across all symbols' correlation/black-swan filters.
    """
    cfg = _get_config(request)
    src = _adm.get_data_source()
    adapter = _adm.get_adapter() or request.app.state.adapter
    now_ms = int(time.time() * 1000)

    instruments = [i for i in registry.list_instruments() if _adapter_can_serve(i, src)]

    # Shared BTC reference (fetched once).
    btc = None
    binst = registry.get_instrument("BTC")
    if binst and _adapter_can_serve(binst, src):
        try:
            btc = await adapter.get_candles(binst, "1H", limit=900)
        except Exception:
            btc = None

    sem = asyncio.Semaphore(6)

    async def _one(inst) -> SignalSummary:
        sym = inst.underlying
        async with sem:
            try:
                c1h = await adapter.get_candles(inst, "1H", limit=900)
                c4h = await adapter.get_candles(inst, "4H", limit=220)
            except Exception as exc:
                return SignalSummary(
                    underlying=sym, close=0.0, direction="none", entry_ok=False,
                    arrow=False, consensus_count=0, quality_total=0.0, quality_pass=False,
                    regime_label="error", effective_mode=cfg.mode, asset_class=AssetClass.LARGE,
                    reason="candle fetch failed", error=str(exc)[:80], timestamp_ms=now_ms,
                )
        ref_btc = c1h if sym == "BTC" else btc
        ev = bt.evaluate_live(sym, c1h, c4h, ref_btc, cfg)
        return _to_summary(ev)

    results: List[SignalSummary] = await asyncio.gather(*[_one(i) for i in instruments])

    # Armed first, then highest quality, then by |consensus|.
    results.sort(key=lambda s: (s.entry_ok, s.quality_total, s.consensus_count), reverse=True)
    if armed_only:
        results = [s for s in results if s.entry_ok]

    return SignalScanResponse(
        signals=results, count=len(results),
        armed_count=sum(1 for s in results if s.entry_ok),
        effective_mode=cfg.mode, timestamp_ms=now_ms,
    )


@router.get("/evaluate/{underlying}", response_model=StrategyEvaluation)
async def evaluate(underlying: str, request: Request) -> StrategyEvaluation:
    sym = underlying.upper()
    cfg = _get_config(request)
    _inst, c1h, c4h, btc = await _fetch_candles(request, sym, lookback_days=30)
    return bt.evaluate_live(sym, c1h, c4h, btc, cfg)


# ─── backtest ────────────────────────────────────────────────────────────────


def _store_candles(sym: str, resolution: str, lookback_days: int):
    """Load candles from the local OHLCV store (years of history) as `Candle`s.

    The live adapter caps at ~5000 bars/request (~208 days of 1H); the store
    holds ~2 years, so long backtests read from here. Store keys are `<SYM>USD`
    with lowercase resolutions and `time` in seconds.
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

    # Prefer the local store (deep history). Fall back to the live adapter when
    # the store has too little for this symbol.
    c1h = _store_candles(sym, "1h", body.lookback_days)
    c4h = _store_candles(sym, "4h", body.lookback_days)
    btc = c1h if sym == "BTC" else _store_candles("BTC", "1h", body.lookback_days)

    if len(c1h) < cfg.warmup_bars + 50:
        _inst, c1h, c4h, btc = await _fetch_candles(request, sym, body.lookback_days)

    return bt.run_backtest(sym, c1h, c4h, btc, cfg, body.lookback_days)


# ─── execute (route live trade plan through the existing order path) ─────────


@router.post("/execute", response_model=ExecuteResponse)
async def execute(body: ExecuteRequest, request: Request) -> ExecuteResponse:
    sym = body.underlying.upper()
    cfg = _get_config(request)
    _inst, c1h, c4h, btc = await _fetch_candles(request, sym, lookback_days=30)
    ev = bt.evaluate_live(sym, c1h, c4h, btc, cfg)

    now_ms = int(time.time() * 1000)
    # Execution is always an explicit operator action, so we don't require the
    # strict auto-arm (entry_ok). We need a directional plan and no hard
    # capital-protection halt (daily-loss / circuit-breaker / black-swan).
    if ev.trade_plan is None:
        return ExecuteResponse(
            accepted=False, mode="paper", underlying=sym, direction=ev.direction,
            size_units=0.0, notional_usd=0.0, status="no_direction",
            reason=f"no directional setup: {ev.reason}", timestamp_ms=now_ms,
        )
    if not ev.can_trade:
        return ExecuteResponse(
            accepted=False, mode="paper", underlying=sym, direction=ev.direction,
            size_units=0.0, notional_usd=0.0, status="halted",
            reason=f"capital protection: {ev.block_reason}", timestamp_ms=now_ms,
        )

    plan = ev.trade_plan
    manual = not ev.entry_ok
    # Size in integer contracts; reject sub-1-contract plans.
    contracts = max(0, int(round(plan.size_units)))
    if contracts < 1:
        return ExecuteResponse(
            accepted=False, mode="paper", underlying=sym, direction=plan.direction,
            size_units=plan.size_units, notional_usd=plan.notional_usd, status="size_too_small",
            reason="sized below 1 contract", timestamp_ms=now_ms,
        )

    # Delegate to the existing live/paper order path (reuses safety + brackets).
    from app.api.v1.endpoints.trading import LiveOrderRequest, place_live_order

    order = LiveOrderRequest(
        underlying=sym, direction=plan.direction, instrument_type="futures",
        size=float(contracts), leverage=plan.leverage, order_type="market",
        stop_loss=plan.stop_loss, take_profit=plan.take_profit,
        notes=f"[TRIPLE-ST{'/MANUAL' if manual else ''}] {ev.effective_mode.value} "
              f"Q={ev.quality.total:.0f} {ev.consensus_count}/3ST",
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
