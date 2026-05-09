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
from app.services import snapshot_cache as _snap_cache
from app.services import alert_service as _alert_service
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
from app.services import adapter_manager as _adm

log = get_logger(__name__)
router = APIRouter(prefix="/directional", tags=["directional"])


def _build_indicator_lines(candles):
    """
    Compute supertrend and EMA50 line arrays for chart overlays.
    Returns (st1_line, st2_line, st3_line, ema50_line) — each a list of {time, value}.
    """
    import numpy as np
    from app.engines.indicators.supertrend import compute_supertrend
    from app.engines.indicators.heikin_ashi import compute_heikin_ashi
    from app.engines.indicators.ema import compute_ema

    if not candles:
        return [], [], [], []

    o = np.array([c.open for c in candles], dtype=np.float64)
    h = np.array([c.high for c in candles], dtype=np.float64)
    l = np.array([c.low for c in candles], dtype=np.float64)
    c = np.array([c.close for c in candles], dtype=np.float64)
    times = [can.timestamp_ms // 1000 for can in candles]

    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)
    st1, _ = compute_supertrend(ha_h, ha_l, ha_c, 7, 3.0)
    st2, _ = compute_supertrend(h, l, c, 14, 2.0)
    st3, _ = compute_supertrend(h, l, c, 21, 1.0)
    ema50 = compute_ema(c, 50)

    def _to_line(values):
        return [
            {"time": t, "value": round(float(v), 4)}
            for t, v in zip(times, values)
            if v != 0.0
        ]

    return _to_line(st1), _to_line(st2), _to_line(st3), _to_line(ema50)


def _adapter(request: Request):
    ad = _adm.get_adapter()
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

    if not _adapter_can_serve(inst, _adm.get_data_source()):
        return DirectionalStatusResponse(
            underlying=sym, loaded=False, paper_mode=settings.paper_trading,
            real_public_data=settings.real_public_data,
            exchange_status=f"not_available_on_{_adm.get_data_source()}",
            has_options=inst.has_options,
            state=TradeState.IDLE, timestamp_ms=now_ms,
        )

    adapter = _adapter(request)
    exchange_ok = await adapter.ping()
    regime = signal = None
    state = TradeState.IDLE

    _mode = getattr(request.app.state, "trading_mode", None) if request else None
    try:
        c4h = await adapter.get_candles(inst, "4H", limit=100)
        c1h = await adapter.get_candles(inst, "1H", limit=200)
        regime = compute_regime(c4h, macro_filter=_mode.macro_filter if _mode else "adx_4h")
        signal = compute_signal(c1h, st_threshold=_mode.st_threshold if _mode else 3)
        setup = evaluate_setup(regime, signal)
        state = setup.state
    except Exception as exc:
        log.warning("Status compute failed for %s: %s", sym, exc)

    atr_pct = regime.atr_percentile if regime else 0.0
    adx_val = regime.adx if regime else 0.0

    return DirectionalStatusResponse(
        underlying=sym, loaded=True,
        paper_mode=settings.paper_trading,
        real_public_data=settings.real_public_data,
        exchange_status="ok" if exchange_ok else "unreachable",
        has_options=inst.has_options,
        regime=regime, signal=signal, state=state,
        timestamp_ms=now_ms,
        atr_percentile=atr_pct,
        adx=adx_val,
    )


# ─── /watchlist ───────────────────────────────────────────────────────────────

async def _watchlist_item(
    inst, adapter,
    macro_filter: str = "adx_4h",
    st_threshold: int = 3,
) -> WatchlistItem:
    now_ms = int(time.time() * 1000)
    try:
        spot = await adapter.get_index_price(inst)
        c4h = await adapter.get_candles(inst, "4H", limit=100)
        c1h = await adapter.get_candles(inst, "1H", limit=200)
        regime = compute_regime(c4h, macro_filter=macro_filter)
        signal = compute_signal(c1h, st_threshold=st_threshold)
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


def _adapter_can_serve(inst, source: str) -> bool:
    """
    Check whether the active data source can serve market data for an instrument.
    Uses instrument-specific symbol fields rather than inst.exchange label,
    since most crypto instruments are multi-exchange.
    """
    if source == "zerodha":
        return inst.exchange == "zerodha"
    if source == "delta_india":
        # Delta India can serve any instrument that has a delta_perp_symbol
        return inst.delta_perp_symbol is not None
    if source == "okx":
        return inst.okx_perp_symbol is not None
    if source == "binance":
        # Binance can serve all non-zerodha crypto instruments
        return inst.exchange != "zerodha"
    if source == "deribit":
        # Deribit serves its own instruments; zerodha instruments not available
        return inst.exchange != "zerodha"
    # Unknown source: attempt and let the adapter fail gracefully
    return inst.exchange != "zerodha"


@router.get("/watchlist", response_model=WatchlistResponse)
async def watchlist(request: Request) -> WatchlistResponse:
    current_source = _adm.get_data_source()
    instruments = registry.list_instruments()
    adapter = _adapter(request)
    now_ms = int(time.time() * 1000)
    _wl_mode = getattr(request.app.state, "trading_mode", None)
    _macro_f = _wl_mode.macro_filter if _wl_mode else "adx_4h"
    _st_thr = _wl_mode.st_threshold if _wl_mode else 3

    async def _item_or_skip(inst) -> WatchlistItem:
        if not _adapter_can_serve(inst, current_source):
            return WatchlistItem(
                underlying=inst.underlying,
                has_options=inst.has_options,
                state=TradeState.IDLE,
                direction=Direction.NEUTRAL,
                error=f"{inst.underlying} not available on {current_source}",
                timestamp_ms=now_ms,
            )
        return await _watchlist_item(inst, adapter,
                                     macro_filter=_macro_f, st_threshold=_st_thr)

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

    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(
            status_code=400,
            detail=f"{sym} is not available on {src} data source",
        )

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

    # Compute IVR: DVOL-based if available, HV-based fallback for non-DVOL sources
    ivr = await compute_ivr(adapter, inst, c1h)

    return MarketSnapshotResponse(
        underlying=sym,
        spot_price=spot, index_price=spot, perp_price=perp,
        candles_4h_count=len(c4h),
        candles_1h_count=len(c1h),
        candles_15m_count=len(c15m),
        dvol=dvol, ivr=ivr,
        data_source=f"{src}/{inst.underlying}",
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
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(
            status_code=400,
            detail=f"{sym} is not available on {src} data source",
        )
    mode = getattr(request.app.state, "trading_mode", None) if request else None
    return await engine_preview(
        inst, _adapter(request),
        macro_filter=mode.macro_filter if mode else "adx_4h",
    )


# ─── /run-once ────────────────────────────────────────────────────────────────

@router.post("/run-once", response_model=RunOnceResponse)
async def run_once_endpoint(
    underlying: Optional[str] = Query(None),
    request: Request = None,
) -> RunOnceResponse:
    from app.core.rate_limit import check_run_once
    check_run_once(request)
    sym = _sym(underlying)
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(
            status_code=400,
            detail=f"{sym} is not available on {src} data source",
        )

    from app.api.v1.endpoints.config import get_runtime_risk
    _mode = getattr(request.app.state, "trading_mode", None) if request else None
    result = await engine_run_once(
        inst, _adapter(request), get_runtime_risk(),
        macro_filter=_mode.macro_filter if _mode else "adx_4h",
    )

    # Record in eval history
    sig = result.signal or {}
    hist_store.record(sym, {
        "state": result.state.value,
        "direction": result.direction.value,
        "recommendation": result.recommendation,
        "no_trade_score": result.no_trade_score,
        "ivr": result.ivr,
        "ivr_band": result.ivr_band.value if result.ivr_band else None,
        "exec_mode": result.exec_mode.value if result.exec_mode else None,
        "signal_trend": sig.get("trend") if isinstance(sig, dict) else None,
        "top_structure": (
            result.ranked_structures[0].structure.structure_type
            if result.ranked_structures else None
        ),
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
    from app.core.rate_limit import check_run_all
    check_run_all(request)
    from app.api.v1.endpoints.config import get_runtime_risk
    src = _adm.get_data_source()
    instruments = [
        i for i in registry.list_instruments()
        if i.has_options and _adapter_can_serve(i, src)
    ]
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
            sig_r = r.signal or {}
            hist_store.record(inst.underlying, {
                "state": r.state.value,
                "direction": r.direction.value,
                "recommendation": r.recommendation,
                "no_trade_score": r.no_trade_score,
                "ivr": r.ivr,
                "ivr_band": r.ivr_band.value if r.ivr_band else None,
                "exec_mode": r.exec_mode.value if r.exec_mode else None,
                "signal_trend": sig_r.get("trend") if isinstance(sig_r, dict) else None,
                "top_structure": (
                    r.ranked_structures[0].structure.structure_type
                    if r.ranked_structures else None
                ),
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

# ─── /signals (cache-only multi-instrument summary) ──────────────────────────

@router.get("/signals")
async def all_signals() -> dict:
    """
    Fast multi-instrument signal summary from in-memory caches only.
    No exchange calls — returns immediately from snapshot_cache + eval_history.
    Refreshes naturally as SSE streams write to the cache.
    """
    instruments = registry.list_instruments()
    results = []
    for inst in instruments:
        sym = inst.underlying
        snap = _snap_cache.get(sym)
        history = hist_store.get_history(sym)
        latest = history[-1] if history else None

        state = 'IDLE'
        direction = 'neutral'
        regime = ''
        score_long = 0.0
        score_short = 0.0
        exec_mode = None
        if latest:
            state = latest.get('state', 'IDLE')
            direction = latest.get('direction', 'neutral')
            regime = latest.get('macro_regime', '')
            score_long = float(latest.get('score_long') or 0.0)
            score_short = float(latest.get('score_short') or 0.0)
            exec_mode = latest.get('exec_mode')
        elif snap:
            state = snap.current_state

        results.append({
            'underlying': sym,
            'has_options': inst.has_options,
            'spot_price': snap.spot_price if snap else None,
            'ivr': snap.ivr if snap else None,
            'green_arrow': snap.green_arrow if snap else False,
            'red_arrow': snap.red_arrow if snap else False,
            'state': state,
            'direction': direction,
            'regime': regime,
            'score_long': round(score_long, 1),
            'score_short': round(score_short, 1),
            'exec_mode': exec_mode,
            'fresh': snap is not None,
            'timestamp_ms': snap.computed_at_ms if snap else 0,
        })

    # Sort: actionable states first
    _ORDER = {
        'ENTRY_ARMED_PULLBACK': 0, 'ENTRY_ARMED_CONTINUATION': 1,
        'CONFIRMED_SETUP_ACTIVE': 2, 'EARLY_SETUP_ACTIVE': 3,
        'FILTERED': 4, 'IDLE': 5,
    }
    results.sort(key=lambda r: _ORDER.get(r['state'], 6))

    return {'signals': results, 'count': len(results), 'timestamp_ms': int(time.time() * 1000)}


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

    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(
            status_code=400,
            detail=f"{sym} is not available on {src} data source",
        )

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

    mode = getattr(request.app.state, "trading_mode", None) if request else None
    macro_filter = mode.macro_filter if mode else "adx_4h"
    st_threshold = mode.st_threshold if mode else 3

    regime = compute_regime(c4h, macro_filter=macro_filter)
    signal = compute_signal(c1h, st_threshold=st_threshold)
    setup = evaluate_setup(regime, signal)
    exec_timing = assess_timing(c15m, signal, atr_pct=regime.atr_percentile)
    ivr = await compute_ivr(adapter, inst, c1h)

    from app.engines.directional.policy_engine import apply_policy
    policy = apply_policy(setup.direction, inst, ivr)

    # Build indicator lines for the chart overlay
    st1_line, st2_line, st3_line, ema50_line = _build_indicator_lines(c1h)

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
        atr_percentile=regime.atr_percentile,
        adx=regime.adx,
        st1_line=st1_line,
        st2_line=st2_line,
        st3_line=st3_line,
        ema50_line=ema50_line,
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

    # Track previous alert state across iterations for rising-edge detection.
    # Without this, a sustained all_green condition fires alerts every 30s
    # but never records an arrow because signal.green_arrow (transition) is False.
    _prev_alert_green = False
    _prev_alert_red = False

    while True:
        if await request.is_disconnected():
            break
        # Re-fetch adapter each iteration — handles hot-swap of data source
        adapter = _adapter(request)
        src = _adm.get_data_source()
        if not _adapter_can_serve(inst, src):
            yield f"data: {json.dumps({'underlying': sym, 'error': f'{sym} not available on {src}', 'timestamp_ms': int(time.time() * 1000)})}\n\n"
            await asyncio.sleep(interval)
            continue
        try:
            _mode = getattr(request.app.state, "trading_mode", None)
            _macro_filter = _mode.macro_filter if _mode else "adx_4h"
            _st_threshold = _mode.st_threshold if _mode else 3

            c4h = await adapter.get_candles(inst, "4H", limit=100)
            c1h = await adapter.get_candles(inst, "1H", limit=200)
            regime = compute_regime(c4h, macro_filter=_macro_filter)
            signal = compute_signal(c1h, st_threshold=_st_threshold)
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
            # Expanded alert condition: transition OR sustained alignment in actionable state.
            # This ensures signal_green_arrow alerts fire even when the user missed
            # the exact transition bar (e.g. stream started mid-trend).
            _actionable = {
                "CONFIRMED_SETUP_ACTIVE", "ENTRY_ARMED_PULLBACK",
                "ENTRY_ARMED_CONTINUATION", "EARLY_SETUP_ACTIVE",
            }
            _alert_green = signal.green_arrow or (signal.all_green and setup.state.value in _actionable)
            _alert_red   = signal.red_arrow   or (signal.all_red   and setup.state.value in _actionable)

            # Record arrow on the RISING EDGE of the expanded condition.
            # Without previous-state tracking, sustained all_green fires alerts
            # every 30s but records zero arrows — FIRED counter and ARROWS counter diverge.
            if _alert_green and not _prev_alert_green:
                arrow_store.record(sym, "green", float(spot), setup.direction.value,
                                   setup.state.value, now_ms, "stream")
            elif _alert_red and not _prev_alert_red:
                arrow_store.record(sym, "red", float(spot), setup.direction.value,
                                   setup.state.value, now_ms, "stream")
            _prev_alert_green = _alert_green
            _prev_alert_red   = _alert_red

            # Also expose the expanded condition in the payload so ArrowAlert popup
            # and the frontend know a live signal is active.
            payload["green_arrow"] = _alert_green
            payload["red_arrow"]   = _alert_red
            payload["signal_active"] = _alert_green or _alert_red

            # Record actionable states to eval_history (not IDLE/FILTERED) so
            # EvalHistoryPanel fills up from the live stream, not just run-once.
            if setup.state.value not in ("IDLE", "FILTERED"):
                hist_store.record(sym, {
                    "state": setup.state.value,
                    "direction": setup.direction.value,
                    "recommendation": "stream",
                    "no_trade_score": 0.0,
                    "ivr": ivr,
                    "ivr_band": None,
                    "exec_mode": None,
                    "signal_trend": signal.trend,
                    "top_structure": None,
                    "timestamp_ms": now_ms,
                })

            # Update snapshot cache using expanded condition so background poller
            # fires alerts consistently with the SSE stream.
            _snap_cache.put(
                sym=sym,
                spot_price=float(spot),
                ivr=ivr,
                green_arrow=_alert_green,
                red_arrow=_alert_red,
                current_state=setup.state.value,
            )

            # Check and fire all triggered alerts; deliver webhooks (non-blocking)
            fired = await _alert_service.check_and_fire(
                sym=sym,
                spot_price=float(spot),
                ivr=ivr,
                green_arrow=_alert_green,
                red_arrow=_alert_red,
                current_state=setup.state.value,
            )
            if fired:
                payload["alert_fired"] = fired[0]
                payload["alerts_fired"] = fired

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
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(status_code=400, detail=f"{sym} not available on {src}")

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
    from app.core.rate_limit import check_run_once
    check_run_once(request)
    sym = _sym(underlying)
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(status_code=400, detail=f"{sym} not available on {src}")
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
