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
    StrategyEvaluation, ConfigResponse, UniverseResponse,
    BacktestRequest, TripleSTBacktestResult, ExecuteRequest, ExecuteResponse,
    SignalSummary, SignalScanResponse, HistoryTrade, HistoryResponse,
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


@router.get("/universe", response_model=UniverseResponse)
async def universe(request: Request) -> UniverseResponse:
    """Selectable underlyings — every stored coin with enough daily history."""
    cfg = _get_config(request)
    syms = await asyncio.to_thread(_store_symbols, cfg.trend_sma_period * 24)
    return UniverseResponse(symbols=syms)


# ─── candle fetch (daily) ────────────────────────────────────────────────────


def _daily_limit(cfg: TripleSTConfig) -> int:
    """Daily bars to fetch: trend-SMA period + warm-up + a comfortable buffer."""
    return min(cfg.trend_sma_period + cfg.warmup_bars + 80, 1000)


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
        sma=ev.sma, rsi=ev.rsi, rsi_oversold=ev.rsi_oversold, rsi_exit=ev.rsi_exit,
        in_uptrend=ev.in_uptrend, oversold=ev.oversold,
        entry=p.entry if p else None, stop_loss=p.stop_loss if p else None,
        r_distance=p.r_distance if p else None,
        risk_pct=p.risk_pct if p else None, leverage=p.leverage if p else None,
        notional_usd=p.notional_usd if p else None, size_units=p.size_units if p else None,
        reason=ev.reason, timestamp_ms=ev.timestamp_ms,
    )


def _store_symbols(min_1h_bars: int) -> List[str]:
    """Every crypto underlying with enough stored 1H history (keys are <SYM>USD)."""
    from app.services import ohlcv_store
    syms = set()
    for r in ohlcv_store.get_status():
        if r.get("resolution") == "1h" and r.get("count", 0) >= min_1h_bars:
            s = r["symbol"]
            syms.add(s[:-3] if s.endswith("USD") else s)
    return sorted(syms)


def _scan_universe(cfg: TripleSTConfig, src: str, now_ms: int) -> List[SignalSummary]:
    """Evaluate the whole stored-crypto universe off the local OHLCV store.

    The store is fresh (updated hourly) and is the same universe the strategy
    was validated on, so it gives full coverage without depending on the live
    adapter's small registered-instrument list. Symbols that are NOT registered
    tradeable instruments on the active data source are returned as signal-only
    (executable=False) — they can't be routed to a live/paper order.

    Sync (sqlite + numpy); call via asyncio.to_thread so the event loop is free.
    """
    days = max(cfg.trend_sma_period, cfg.warmup_bars) + 60
    if cfg.symbols:
        # Explicit allowlist — scan exactly these (thin ones surface as warming).
        universe = [s.upper() for s in cfg.symbols]
    else:
        universe = _store_symbols(min_1h_bars=cfg.warmup_bars * 24)
    out: List[SignalSummary] = []
    for sym in universe:
        try:
            candles = _store_candles(sym, "1h", days)
            ev = bt.evaluate_live(sym, candles, cfg)
            summ = _to_summary(ev)
        except Exception as exc:
            out.append(SignalSummary(
                underlying=sym, close=0.0, direction="none", entry_ok=False,
                reason="evaluation failed", error=str(exc)[:80], timestamp_ms=now_ms,
            ))
            continue
        inst = registry.get_instrument(sym)
        tradeable = bool(inst and _adapter_can_serve(inst, src))
        if not tradeable:
            summ.executable = False
            if summ.entry_ok:
                summ.reason = f"{summ.reason} · signal-only (not on {src})"
        out.append(summ)
    return out


# Scan cache: the universe scan resamples ~55 coins of 1H history (GIL-heavy,
# ~6s). Signals derive from the last *closed* daily bar, so they only change
# once per day — a short TTL is plenty fresh and keeps the event loop free even
# while the UI polls every 30s. A single-flight lock prevents overlapping scans.
_SCAN_TTL = 120.0
_scan_cache: dict = {"key": None, "ts": 0.0, "data": []}
_scan_lock = asyncio.Lock()


@router.get("/signals", response_model=SignalScanResponse)
async def signals(request: Request, armed_only: bool = False) -> SignalScanResponse:
    """Scan the full stored-crypto universe and return a compact signal per symbol.

    Registered instruments on the active data source are executable; the rest are
    signal-only (data from the local store). Results are cached for `_SCAN_TTL`s.
    """
    import time as _t
    cfg = _get_config(request)
    src = _adm.get_data_source()
    now_ms = int(time.time() * 1000)
    key = (cfg.model_dump_json(), src)

    def _fresh() -> bool:
        return _scan_cache["key"] == key and (_t.monotonic() - _scan_cache["ts"]) < _SCAN_TTL

    if not _fresh():
        async with _scan_lock:
            if not _fresh():                       # re-check after waiting for the lock
                data = await asyncio.to_thread(_scan_universe, cfg, src, now_ms)
                # Most actionable first: armed → in-uptrend coins closest to the
                # oversold trigger → everything else.
                data.sort(key=lambda s: (0 if s.entry_ok else 1, 0 if s.in_uptrend else 1, s.rsi))
                _scan_cache.update(key=key, ts=_t.monotonic(), data=data)

    results: List[SignalSummary] = _scan_cache["data"]
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


# ─── recent signal history (completed trades across the universe) ────────────

_HISTORY_TTL = 600.0
_history_cache: dict = {"key": None, "ts": 0.0, "data": []}
_history_lock = asyncio.Lock()


def _scan_history(cfg: TripleSTConfig, lookback_days: int, limit: int) -> List[HistoryTrade]:
    """Replay every scanned coin and collect the most recent completed trades."""
    if cfg.symbols:
        universe = [s.upper() for s in cfg.symbols]
    else:
        universe = _store_symbols(min_1h_bars=cfg.warmup_bars * 24)
    fetch_days = cfg.trend_sma_period + lookback_days + 30
    rows: List[HistoryTrade] = []
    for sym in universe:
        try:
            candles = _store_candles(sym, "1h", fetch_days)
            res = bt.run_backtest(sym, candles, cfg, lookback_days)
        except Exception:
            continue
        for t in res.trades:
            rows.append(HistoryTrade(
                underlying=sym, direction=t.direction, entry_ts=t.entry_ts,
                exit_ts=t.exit_ts, entry_price=t.entry_price, exit_price=t.exit_price,
                bars_held=t.bars_held, pnl_r=t.pnl_r, exit_reason=t.exit_reason,
            ))
    rows.sort(key=lambda t: t.entry_ts, reverse=True)
    return rows[:limit]


@router.get("/history", response_model=HistoryResponse)
async def history(request: Request, lookback_days: int = 365, limit: int = 80) -> HistoryResponse:
    """Most recent completed trades across the scanned universe (cached ~10 min).

    Heavy (replays every coin), so it's loaded on demand by the UI panel.
    """
    import time as _t
    lookback_days = max(30, min(lookback_days, 1095))
    limit = max(1, min(limit, 200))
    cfg = _get_config(request)
    key = (cfg.model_dump_json(), lookback_days, limit)

    def _fresh() -> bool:
        return _history_cache["key"] == key and (_t.monotonic() - _history_cache["ts"]) < _HISTORY_TTL

    if not _fresh():
        async with _history_lock:
            if not _fresh():
                data = await asyncio.to_thread(_scan_history, cfg, lookback_days, limit)
                _history_cache.update(key=key, ts=_t.monotonic(), data=data)

    trades: List[HistoryTrade] = _history_cache["data"]
    wins = sum(1 for t in trades if t.pnl_r > 0)
    return HistoryResponse(
        trades=trades, count=len(trades), wins=wins,
        win_rate=round(wins / len(trades), 3) if trades else 0.0,
        timestamp_ms=int(time.time() * 1000),
    )


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
        notes=f"[RSI2-MEANREV] {plan.direction} RSI={ev.rsi:.0f} "
              f"(buy<{ev.rsi_oversold:.0f}, exit>{ev.rsi_exit:.0f})",
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
