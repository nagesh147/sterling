import asyncio
import json
import time
from typing import Optional, AsyncGenerator, List

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.schemas.directional import (
    DirectionalStatusResponse, TradeState, WatchlistResponse,
    WatchlistItem, IVRBand, Direction, MacroRegime,
    EvalHistoryResponse, EvalHistoryItem,
)
from app.schemas.snapshot import DirectionalSnapshot
from app.schemas.regime_trend import RegimeTrendResponse, RegimeTrendBar
from app.engines.directional.execution_engine import assess_timing
from app.schemas.execution import RunOnceResponse, PreviewResponse
from app.schemas.market import MarketSnapshotResponse
from app.services.exchanges import instrument_registry as registry
from app.services import eval_history as hist_store
from app.services import arrow_store
from app.services import alert_store as _alert_store
from app.engines.directional.orchestrator import (
    run_once as engine_run_once,
    preview as engine_preview,
    compute_ivr,
)
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/directional", tags=["directional"])


def _adapter(request: Request):
    from app.services import adapter_manager
    ad = adapter_manager.get_adapter()
    return ad if ad is not None else request.app.state.adapter


def _sym(underlying: Optional[str]) -> str:
    return (underlying or settings.default_underlying).upper()


# ─── /status ──────────────────────────────────────────────────────────────────

@router.get("/status", response_model=DirectionalStatusResponse)
async def directional_status(
    underlying: Optional[str] = Query(None),
    request: Request = None,
) -> DirectionalStatusResponse:
    sym = _sym(underlying)
    inst = registry.get_instrument(sym)
    now_ms = int(time.time() * 1000)

    if not inst:
        return DirectionalStatusResponse(
            underlying=sym, loaded=False, paper_mode=settings.paper_trading,
            real_public_data=settings.real_public_data,
            exchange_status="unknown", has_options=False,
            state=TradeState.IDLE, timestamp_ms=now_ms,
        )

    adapter = _adapter(request)
    exchange_ok = await adapter.ping()
    regime = signal = None
    state = TradeState.IDLE

    try:
        c4h = await adapter.get_candles(inst, "4H", limit=100)
        c1h = await adapter.get_candles(inst, "1H", limit=200)
        regime = compute_regime(c4h)
        signal = compute_signal(c1h)
        setup = evaluate_setup(regime, signal)
        state = setup.state
    except Exception as exc:
        log.warning("Status compute failed for %s: %s", sym, exc)

    return DirectionalStatusResponse(
        underlying=sym, loaded=True,
        paper_mode=settings.paper_trading,
        real_public_data=settings.real_public_data,
        exchange_status="ok" if exchange_ok else "unreachable",
        has_options=inst.has_options,
        regime=regime, signal=signal, state=state,
        timestamp_ms=now_ms,
    )


# ─── /watchlist ───────────────────────────────────────────────────────────────

async def _watchlist_item(inst, adapter) -> WatchlistItem:
    now_ms = int(time.time() * 1000)
    try:
        spot = await adapter.get_index_price(inst)
        c4h = await adapter.get_candles(inst, "4H", limit=100)
        c1h = await adapter.get_candles(inst, "1H", limit=200)
        regime = compute_regime(c4h)
        signal = compute_signal(c1h)
        setup = evaluate_setup(regime, signal)
        ivr = await compute_ivr(adapter, inst, c1h)
        from app.engines.directional.policy_engine import apply_policy
        policy = apply_policy(setup.direction, inst, ivr)
        return WatchlistItem(
            underlying=inst.underlying,
            has_options=inst.has_options,
            state=setup.state,
            direction=setup.direction,
            macro_regime=regime.macro_regime,
            signal_trend=signal.trend,
            ivr=ivr,
            ivr_band=policy.ivr_band,
            score_long=signal.score_long,
            score_short=signal.score_short,
            spot_price=spot,
            timestamp_ms=now_ms,
        )
    except Exception as exc:
        return WatchlistItem(
            underlying=inst.underlying,
            has_options=inst.has_options,
            state=TradeState.IDLE,
            direction=Direction.NEUTRAL,
            error=str(exc),
            timestamp_ms=now_ms,
        )


@router.get("/watchlist", response_model=WatchlistResponse)
async def watchlist(request: Request) -> WatchlistResponse:
    from app.services import adapter_manager as _adm
    current_source = _adm.get_data_source()

    # Exchange compatibility map: which adapters can serve each exchange's instruments
    _exchange_sources: dict[str, list[str]] = {
        "deribit":     ["deribit", "okx"],
        "okx":         ["okx", "deribit"],
        "binance":     ["binance", "deribit", "okx"],
        "zerodha":     ["zerodha"],
        "delta_india": ["delta_india", "deribit", "binance"],
    }

    def _is_compatible(inst) -> bool:
        compatible = _exchange_sources.get(inst.exchange, [inst.exchange])
        return current_source in compatible

    instruments = registry.list_instruments()
    adapter = _adapter(request)
    now_ms = int(time.time() * 1000)

    async def _item_or_skip(inst) -> WatchlistItem:
        if not _is_compatible(inst):
            return WatchlistItem(
                underlying=inst.underlying,
                has_options=inst.has_options,
                state=TradeState.IDLE,
                direction=Direction.NEUTRAL,
                error=f"Not available on {current_source} (requires {inst.exchange})",
                timestamp_ms=now_ms,
            )
        return await _watchlist_item(inst, adapter)

    results = await asyncio.gather(
        *[_item_or_skip(inst) for inst in instruments],
        return_exceptions=False,
    )
    items = list(results)
    return WatchlistResponse(items=items, count=len(items), timestamp_ms=now_ms)


# ─── /debug/market-snapshot ───────────────────────────────────────────────────

@router.get("/debug/market-snapshot", response_model=MarketSnapshotResponse)
async def market_snapshot(
    underlying: Optional[str] = Query(None),
    request: Request = None,
) -> MarketSnapshotResponse:
    sym = _sym(underlying)
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    adapter = _adapter(request)
    now_ms = int(time.time() * 1000)

    try:
        spot = await adapter.get_index_price(inst)
        perp = await adapter.get_perp_price(inst)
        c4h = await adapter.get_candles(inst, "4H", limit=100)
        c1h = await adapter.get_candles(inst, "1H", limit=200)
        c15m = await adapter.get_candles(inst, "15m", limit=50)
        dvol = await adapter.get_dvol(inst)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market data fetch failed: {exc}")

    dvol_hist = await adapter.get_dvol_history(inst, days=30)
    ivr = None
    if dvol and dvol_hist:
        lo, hi = min(dvol_hist), max(dvol_hist)
        if hi > lo:
            ivr = round((dvol - lo) / (hi - lo) * 100.0, 2)

    return MarketSnapshotResponse(
        underlying=sym,
        spot_price=spot, index_price=spot, perp_price=perp,
        candles_4h_count=len(c4h),
        candles_1h_count=len(c1h),
        candles_15m_count=len(c15m),
        dvol=dvol, ivr=ivr,
        data_source=f"deribit_public/{inst.index_name}",
        timestamp_ms=now_ms,
    )


# ─── /preview ─────────────────────────────────────────────────────────────────

@router.get("/preview", response_model=PreviewResponse)
async def preview(
    underlying: Optional[str] = Query(None),
    request: Request = None,
) -> PreviewResponse:
    sym = _sym(underlying)
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")
    return await engine_preview(inst, _adapter(request))


# ─── /run-once ────────────────────────────────────────────────────────────────

@router.post("/run-once", response_model=RunOnceResponse)
async def run_once_endpoint(
    underlying: Optional[str] = Query(None),
    request: Request = None,
) -> RunOnceResponse:
    sym = _sym(underlying)
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    from app.api.v1.endpoints.config import get_runtime_risk
    result = await engine_run_once(inst, _adapter(request), get_runtime_risk())

    # Record in eval history
    hist_store.record(sym, {
        "state": result.state.value,
        "direction": result.direction.value,
        "recommendation": result.recommendation,
        "no_trade_score": result.no_trade_score,
        "ivr": result.ivr,
        "timestamp_ms": result.timestamp_ms,
    })

    # Record arrow events from run-once
    if result.signal:
        sig = result.signal
        spot = 0.0
        if result.regime:
            spot = result.regime.get("close_4h", 0.0)
        if sig.get("green_arrow"):
            arrow_store.record(sym, "green", spot, result.direction.value,
                               result.state.value, result.timestamp_ms, "run_once")
        elif sig.get("red_arrow"):
            arrow_store.record(sym, "red", spot, result.direction.value,
                               result.state.value, result.timestamp_ms, "run_once")

    return result


# ─── /run-all ────────────────────────────────────────────────────────────────

@router.post("/run-all")
async def run_all_endpoint(request: Request):
    """
    Parallel run-once for ALL instruments that have options.
    Returns results dict keyed by underlying.
    """
    from app.api.v1.endpoints.config import get_runtime_risk
    instruments = [i for i in registry.list_instruments() if i.has_options]
    adapter = _adapter(request)
    risk = get_runtime_risk()
    now_ms = int(time.time() * 1000)

    raw = await asyncio.gather(
        *[engine_run_once(inst, adapter, risk) for inst in instruments],
        return_exceptions=True,
    )

    results = {}
    for inst, r in zip(instruments, raw):
        if isinstance(r, Exception):
            results[inst.underlying] = {"error": str(r)}
        else:
            # Record in eval history
            hist_store.record(inst.underlying, {
                "state": r.state.value,
                "direction": r.direction.value,
                "recommendation": r.recommendation,
                "no_trade_score": r.no_trade_score,
                "ivr": r.ivr,
                "timestamp_ms": r.timestamp_ms,
            })
            results[inst.underlying] = {
                "state": r.state.value,
                "direction": r.direction.value,
                "recommendation": r.recommendation,
                "no_trade_score": r.no_trade_score,
                "exec_mode": r.exec_mode.value,
                "top_structure": r.ranked_structures[0].structure.structure_type
                    if r.ranked_structures else None,
            }

    return {
        "results": results,
        "instruments_evaluated": len(instruments),
        "timestamp_ms": now_ms,
    }


# ─── /history/{underlying} ───────────────────────────────────────────────────

# ─── /snapshot ────────────────────────────────────────────────────────────────

@router.get("/snapshot", response_model=DirectionalSnapshot)
async def snapshot(
    underlying: Optional[str] = Query(None),
    request: Request = None,
) -> DirectionalSnapshot:
    """
    Single-call comprehensive directional state.
    Returns regime + signal + setup + exec timing + IVR in one response.
    Use instead of polling /status + /debug/market-snapshot separately.
    """
    sym = _sym(underlying)
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    adapter = _adapter(request)
    now_ms = int(time.time() * 1000)

    try:
        spot, perp, c4h, c1h, c15m = await asyncio.gather(
            adapter.get_index_price(inst),
            adapter.get_perp_price(inst),
            adapter.get_candles(inst, "4H", limit=100),
            adapter.get_candles(inst, "1H", limit=200),
            adapter.get_candles(inst, "15m", limit=50),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {exc}")

    regime = compute_regime(c4h)
    signal = compute_signal(c1h)
    setup = evaluate_setup(regime, signal)
    exec_timing = assess_timing(c15m, signal)
    ivr = await compute_ivr(adapter, inst, c1h)

    from app.engines.directional.policy_engine import apply_policy
    policy = apply_policy(setup.direction, inst, ivr)

    return DirectionalSnapshot(
        underlying=sym,
        spot_price=float(spot),
        perp_price=float(perp),
        macro_regime=regime.macro_regime.value,
        ema50=regime.ema50,
        regime_score=regime.score,
        signal_trend=signal.trend,
        all_green=signal.all_green,
        all_red=signal.all_red,
        green_arrow=signal.green_arrow,
        red_arrow=signal.red_arrow,
        st_trends=signal.st_trends,
        st_values=signal.st_values,
        score_long=signal.score_long,
        score_short=signal.score_short,
        close_1h=signal.close_1h,
        ivr=ivr,
        ivr_band=policy.ivr_band,
        state=setup.state,
        direction=setup.direction.value,
        setup_reason=setup.reason,
        exec_mode=exec_timing.mode.value,
        exec_confidence=exec_timing.confidence,
        exec_reason=exec_timing.reason,
        timestamp_ms=now_ms,
    )


# ─── /history/{underlying} ────────────────────────────────────────────────────

@router.get("/history/{underlying}", response_model=EvalHistoryResponse)
async def eval_history(underlying: str) -> EvalHistoryResponse:
    sym = underlying.upper()
    if not registry.is_supported(sym):
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")
    entries = hist_store.get_history(sym)
    items = [EvalHistoryItem(**e) for e in entries]
    return EvalHistoryResponse(underlying=sym, history=items, count=len(items))


# ─── /stream/{underlying} (SSE) ───────────────────────────────────────────────

async def _sse_generator(
    sym: str,
    request: Request,
    interval: float = 30.0,
) -> AsyncGenerator[str, None]:
    inst = registry.get_instrument(sym)
    if not inst:
        yield f"data: {json.dumps({'error': f'Unknown underlying: {sym}'})}\n\n"
        return

    adapter = _adapter(request)

    while True:
        if await request.is_disconnected():
            break
        try:
            c4h = await adapter.get_candles(inst, "4H", limit=100)
            c1h = await adapter.get_candles(inst, "1H", limit=200)
            regime = compute_regime(c4h)
            signal = compute_signal(c1h)
            setup = evaluate_setup(regime, signal)
            ivr = await compute_ivr(adapter, inst, c1h)
            spot = await adapter.get_index_price(inst)
            now_ms = int(time.time() * 1000)
            payload = {
                "underlying": sym,
                "state": setup.state.value,
                "direction": setup.direction.value,
                "macro_regime": regime.macro_regime.value,
                "signal_trend": signal.trend,
                "all_green": signal.all_green,
                "all_red": signal.all_red,
                "green_arrow": signal.green_arrow,
                "red_arrow": signal.red_arrow,
                "st_trends": signal.st_trends,
                "score_long": signal.score_long,
                "score_short": signal.score_short,
                "ivr": ivr,
                "spot_price": float(spot),
                "timestamp_ms": now_ms,
            }
            # Record arrows from live stream
            if signal.green_arrow:
                arrow_store.record(sym, "green", float(spot), setup.direction.value,
                                   setup.state.value, now_ms, "stream")
            elif signal.red_arrow:
                arrow_store.record(sym, "red", float(spot), setup.direction.value,
                                   setup.state.value, now_ms, "stream")

            # Rearm cooldown-expired alerts, then check all active ones
            for a in _alert_store.list_alerts(sym):
                _alert_store.rearm_if_cooldown_elapsed(a.id)

            for alert in _alert_store.list_alerts(sym):
                if alert.status.value != "active":
                    continue
                result = _alert_store.check_alert(
                    alert,
                    spot_price=float(spot),
                    ivr=ivr,
                    green_arrow=signal.green_arrow,
                    red_arrow=signal.red_arrow,
                    current_state=setup.state.value,
                )
                if result.triggered:
                    _alert_store.fire_alert(alert.id, trigger_value=result.current_value)
                    payload["alert_fired"] = {
                        "id": alert.id, "condition": alert.condition.value,
                        "message": result.message,
                    }

        except Exception as exc:
            payload = {"underlying": sym, "error": str(exc), "timestamp_ms": int(time.time() * 1000)}

        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(interval)


@router.get("/stream/{underlying}")
async def stream_directional(
    underlying: str,
    request: Request,
    interval: float = Query(30.0, ge=5.0, le=300.0),
):
    sym = underlying.upper()
    return StreamingResponse(
        _sse_generator(sym, request, interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ─── /arrows/{underlying} ─────────────────────────────────────────────────────


class ArrowResponse(BaseModel):
    underlying: str
    arrows: List[dict]
    count: int


@router.get("/arrows/{underlying}", response_model=ArrowResponse)
async def get_arrows(underlying: str) -> ArrowResponse:
    sym = underlying.upper()
    if not registry.is_supported(sym):
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")
    events = arrow_store.get_arrows(sym)
    return ArrowResponse(
        underlying=sym,
        arrows=[e.model_dump() for e in events],
        count=len(events),
    )


@router.get("/arrows", response_model=ArrowResponse)
async def get_all_arrows() -> ArrowResponse:
    events = arrow_store.get_all()
    return ArrowResponse(
        underlying="ALL",
        arrows=[e.model_dump() for e in events],
        count=len(events),
    )


# ─── /regime-trend/{underlying} ───────────────────────────────────────────────

@router.get("/regime-trend/{underlying}", response_model=RegimeTrendResponse)
async def regime_trend(
    underlying: str,
    n_bars: int = Query(default=30, ge=5, le=100),
    request: Request = None,
) -> RegimeTrendResponse:
    """
    Returns the last n_bars of 4H candles with EMA50 and regime per bar.
    Use for sparkline / regime history visualization.
    """
    import numpy as np
    sym = underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    adapter = _adapter(request)
    try:
        candles_4h = await adapter.get_candles(inst, "4H", limit=100)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}")

    if not candles_4h:
        return RegimeTrendResponse(underlying=sym, bars=[], count=0)

    from app.engines.indicators.ema import compute_ema
    closes = np.array([c.close for c in candles_4h], dtype=np.float64)
    ema50 = compute_ema(closes, 50)

    bars = []
    recent = candles_4h[-n_bars:]
    offset = len(candles_4h) - len(recent)

    for i, candle in enumerate(recent):
        idx = offset + i
        e = float(ema50[idx])
        c = float(candle.close)
        if e == 0:
            regime = "neutral"
            is_bullish = False
        elif c > e:
            regime = "bullish"
            is_bullish = True
        else:
            regime = "bearish"
            is_bullish = False

        bars.append(RegimeTrendBar(
            timestamp_ms=candle.timestamp_ms,
            close=round(c, 4),
            ema50=round(e, 4),
            is_bullish=is_bullish,
            regime=regime,
        ))

    return RegimeTrendResponse(underlying=sym, bars=bars, count=len(bars))


# ─── /volatility-scan ────────────────────────────────────────────────────────

@router.post("/volatility-scan")
async def volatility_scan(
    underlying: Optional[str] = Query(None),
    request: Request = None,
):
    """
    Straddle + strangle analysis — direction-agnostic volatility structures.
    Finds ATM straddle and nearest OTM strangle. Returns IV stats + health.
    Use when signal is mixed but expecting a big move.
    """
    sym = _sym(underlying)
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")
    if not inst.has_options:
        raise HTTPException(status_code=400, detail=f"{sym} has no options")

    adapter = _adapter(request)
    now_ms = int(time.time() * 1000)

    try:
        spot = await adapter.get_index_price(inst)
        chain = await adapter.get_option_chain(inst)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    from app.engines.directional.contract_health_engine import assess_contract_health
    from app.schemas.directional import PolicyResult, IVRBand

    # Filter to healthy contracts, prefer 10-20 DTE
    healthy = [assess_contract_health(o, min_dte=inst.min_dte) for o in chain
               if 5 <= o.dte <= 45]
    healthy = [c for c in healthy if c.healthy]

    calls = sorted([c for c in healthy if c.option_type == "call"], key=lambda x: abs(x.strike - spot))
    puts  = sorted([c for c in healthy if c.option_type == "put"],  key=lambda x: abs(x.strike - spot))

    structures = []

    # ATM Straddle: nearest call + same-strike put
    if calls and puts:
        atm_call = calls[0]
        atm_put = next((p for p in puts if p.strike == atm_call.strike and p.expiry_date == atm_call.expiry_date), None)
        if atm_put:
            debit = atm_call.ask + atm_put.ask
            structures.append({
                "structure_type": "long_straddle",
                "legs": [atm_call.model_dump(), atm_put.model_dump()],
                "strike": atm_call.strike,
                "expiry_date": atm_call.expiry_date,
                "dte": atm_call.dte,
                "net_debit": round(debit, 4),
                "max_loss": round(debit, 4),
                "breakeven_up": round(atm_call.strike + debit, 2),
                "breakeven_down": round(atm_call.strike - debit, 2),
                "avg_iv": round((atm_call.mark_iv + atm_put.mark_iv) / 2, 2),
                "health_score": round((atm_call.health_score + atm_put.health_score) / 2, 2),
            })

    # OTM Strangle: OTM call (strike > spot * 1.02) + OTM put (strike < spot * 0.98)
    otm_calls = [c for c in calls if c.strike > spot * 1.01]
    otm_puts  = [p for p in puts  if p.strike < spot * 0.99]
    if otm_calls and otm_puts:
        sc = otm_calls[0]
        sp = otm_puts[0]
        debit = sc.ask + sp.ask
        if sc.expiry_date == sp.expiry_date:
            structures.append({
                "structure_type": "long_strangle",
                "legs": [sc.model_dump(), sp.model_dump()],
                "call_strike": sc.strike,
                "put_strike": sp.strike,
                "expiry_date": sc.expiry_date,
                "dte": sc.dte,
                "net_debit": round(debit, 4),
                "max_loss": round(debit, 4),
                "breakeven_up": round(sc.strike + debit, 2),
                "breakeven_down": round(sp.strike - debit, 2),
                "avg_iv": round((sc.mark_iv + sp.mark_iv) / 2, 2),
                "health_score": round((sc.health_score + sp.health_score) / 2, 2),
            })

    return {
        "underlying": sym,
        "spot_price": float(spot),
        "structures": structures,
        "healthy_candidates": len(healthy),
        "note": "Use straddle/strangle when expecting large move but uncertain direction.",
        "timestamp_ms": now_ms,
    }
