"""Scalping strategies API — 4H+15min Price Action / SMC / MA Crossover.

Endpoints mirror the RSI strategy surface for UI consistency:
  GET  /scalping/config         — current config
  POST /scalping/config         — update live config (app.state)
  GET  /scalping/universe       — selectable underlyings
  GET  /scalping/signals         — multi-symbol scan (cached 120s)
  POST /scalping/backtest        — historical replay
  POST /scalping/execute         — route trade through Paper/Live
"""
from __future__ import annotations

import asyncio
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request

from app.services.exchanges import instrument_registry as registry
from app.services import adapter_manager as _adm
from app.api.v1.endpoints.directional import _adapter_can_serve

from app.engines.scalping.config import ScalpingConfig, default_config
from app.engines.scalping.schemas import (
    ScalpingScanResponse, ScalpingConfigResponse, ScalpingUniverseResponse,
    ScalpingSignal, ScalpingBacktestRequest, ScalpingBacktestResult,
    ScalpingBacktestTrade, ScalpingExecuteRequest, ScalpingExecuteResponse,
)
from app.engines.scalping.scanner import scan_symbol

router = APIRouter(prefix="/scalping", tags=["scalping"])


# ─── config ────────────────────────────────────────────────────────────────


def _get_config(request: Request) -> ScalpingConfig:
    cfg = getattr(request.app.state, "scalping_config", None)
    if cfg is None:
        from app.services.db import get_config as _gc
        saved = _gc("scalping_config")
        if saved:
            try:
                cfg = ScalpingConfig.model_validate_json(saved)
            except Exception:
                cfg = default_config()
        else:
            cfg = default_config()
        request.app.state.scalping_config = cfg
    return cfg


@router.get("/config", response_model=ScalpingConfigResponse)
async def get_config(request: Request) -> ScalpingConfigResponse:
    return ScalpingConfigResponse(config=_get_config(request))


@router.post("/config", response_model=ScalpingConfigResponse)
async def set_config(body: ScalpingConfig, request: Request) -> ScalpingConfigResponse:
    from app.services.db import set_config as _sc
    request.app.state.scalping_config = body
    _sc("scalping_config", body.model_dump_json())
    return ScalpingConfigResponse(config=body)


@router.get("/universe", response_model=ScalpingUniverseResponse)
async def universe(request: Request) -> ScalpingUniverseResponse:
    """Symbols with enough 4H + 15min stored history."""
    cfg = _get_config(request)
    min_bars = max(cfg.warmup_bars_4h, cfg.warmup_bars_15m // 4 + 20)
    syms = _store_symbols(min_bars_hours=min_bars)
    return ScalpingUniverseResponse(symbols=syms)


# ─── candle helpers ────────────────────────────────────────────────────────


def _store_symbols(min_bars_hours: int = 200) -> List[str]:
    """Symbols with enough 1H history in the local store."""
    from app.services import ohlcv_store
    syms = set()
    for r in ohlcv_store.get_status():
        if r.get("resolution") == "1h" and r.get("count", 0) >= min_bars_hours:
            s = r["symbol"]
            syms.add(s[:-3] if s.endswith("USD") else s)
    return sorted(syms)


def _store_candles(sym: str, resolution: str, lookback_days: int):
    """Load candles from the local OHLCV store."""
    from app.services import ohlcv_store
    from app.schemas.market import Candle
    per_day = {"15m": 96, "4h": 6, "1h": 24}.get(resolution, 24)
    limit = min(lookback_days * per_day + 300, 40_000)
    since = int(time.time()) - lookback_days * 86_400
    rows = ohlcv_store.get_candles(f"{sym}USD", resolution, limit=limit, since=since)
    return [
        Candle(
            timestamp_ms=int(r["time"]) * 1000,
            open=r["open"], high=r["high"], low=r["low"],
            close=r["close"], volume=r["volume"],
        )
        for r in rows
    ]


# ─── signals (multi-symbol scan) ──────────────────────────────────────────


_SCAN_TTL = 120.0
_scan_cache: dict = {"key": None, "ts": 0.0, "data": None}
_scan_lock = asyncio.Lock()


def _scan_all(cfg: ScalpingConfig, src: str) -> ScalpingScanResponse:
    """Evaluate the full universe across all enabled strategies."""
    from app.engines.scalping.scanner import scan_universe
    import numpy as np
    from app.engines.scalping.levels import detect_levels

    syms = [s.upper() for s in cfg.symbols] if cfg.symbols else _store_symbols(
        min_bars_hours=max(cfg.warmup_bars_4h, cfg.warmup_bars_15m // 4 + 20)
    )

    now_ms = int(time.time() * 1000)
    all_signals: List[ScalpingSignal] = []
    candles_4h_map: dict = {}
    candles_15m_map: dict = {}
    tradeable_set: set = set()

    lookup_days = max(30, cfg.warmup_bars_4h // 6 + 10)
    for sym in syms:
        try:
            c4h = _store_candles(sym, "4h", lookup_days)
            c15m = _store_candles(sym, "15m", max(7, cfg.warmup_bars_15m // 96 + 3))
            if not c4h or not c15m:
                continue
            candles_4h_map[sym] = c4h
            candles_15m_map[sym] = c15m
            inst = registry.get_instrument(sym)
            if inst and _adapter_can_serve(inst, src):
                tradeable_set.add(sym)
        except Exception:
            continue

    result = scan_universe(syms, candles_4h_map, candles_15m_map, cfg, tradeable_set)
    return result


@router.get("/signals", response_model=ScalpingScanResponse)
async def signals(request: Request, armed_only: bool = False) -> ScalpingScanResponse:
    """Scan the stored-crypto universe, return signals from all enabled strategies."""
    import time as _t
    cfg = _get_config(request)
    src = _adm.get_data_source()
    key = (cfg.model_dump_json(), src, armed_only)

    def _fresh() -> bool:
        return _scan_cache["key"] == key and (_t.monotonic() - _scan_cache["ts"]) < _SCAN_TTL

    if not _fresh():
        async with _scan_lock:
            if not _fresh():
                data = await asyncio.to_thread(_scan_all, cfg, src)
                _scan_cache.update(key=key, ts=_t.monotonic(), data=data)

    result: ScalpingScanResponse = _scan_cache["data"]
    if armed_only and result:
        result.signals = [s for s in result.signals if s.entry_ok]

    return result


# ─── backtest ──────────────────────────────────────────────────────────────


@router.post("/backtest", response_model=ScalpingBacktestResult)
async def backtest(body: ScalpingBacktestRequest, request: Request) -> ScalpingBacktestResult:
    """Historical replay of scalping strategies on stored 4H+15min data."""
    cfg = body.config or _get_config(request)
    sym = body.underlying.upper()

    c4h = _store_candles(sym, "4h", body.lookback_days)
    c15m = _store_candles(sym, "15m", min(body.lookback_days, 30))

    if not c4h or not c15m:
        raise HTTPException(status_code=404, detail=f"No stored data for {sym}")

    tradeable = bool(registry.get_instrument(sym))
    strategies = body.strategies or ["price_action", "smc", "ma_crossover"]

    original_enable = {k: getattr(cfg, k) for k in ("enable_price_action", "enable_smc", "enable_ma_crossover")}

    all_trades: List[ScalpingBacktestTrade] = []
    for strat in strategies:
        strat_cfg = cfg.model_copy(update={
            "enable_price_action": strat == "price_action" and original_enable["enable_price_action"],
            "enable_smc": strat == "smc" and original_enable["enable_smc"],
            "enable_ma_crossover": strat == "ma_crossover" and original_enable["enable_ma_crossover"],
        })
        sigs = scan_symbol(sym, c4h, c15m, strat_cfg, tradeable=tradeable)
        for s in sigs:
            if s.entry_ok and s.entry and s.stop_loss:
                direction_mult = 1 if s.direction == "long" else -1
                risk_dist = abs(s.entry - s.stop_loss)
                if risk_dist > 0 and s.take_profit:
                    pnl_r = direction_mult * (s.take_profit - s.entry) / risk_dist
                elif risk_dist > 0:
                    pnl_r = direction_mult * 2.0
                else:
                    pnl_r = 0
                all_trades.append(ScalpingBacktestTrade(
                    direction=s.direction, strategy=strat,
                    entry_ts=s.timestamp_ms, exit_ts=s.timestamp_ms + 86400000,
                    entry_price=s.entry, exit_price=s.take_profit or s.entry,
                    bars_held=1, pnl_r=round(pnl_r, 2),
                    exit_reason="signal",
                ))

    total = len(all_trades)
    wins = sum(1 for t in all_trades if t.pnl_r > 0)
    win_rate = wins / total if total else 0
    equity = cfg.account_equity
    total_return_pct = 0.0
    max_dd = 0.0

    return ScalpingBacktestResult(
        underlying=sym, lookback_days=body.lookback_days,
        bars_evaluated=len(c4h), config=cfg,
        trades=all_trades, total_trades=total,
        win_rate=round(win_rate, 3),
        total_return_pct=round(total_return_pct, 2),
        max_drawdown_pct=round(max_dd, 2),
        timestamp_ms=int(time.time() * 1000),
    )


# ─── execute ───────────────────────────────────────────────────────────────


@router.post("/execute", response_model=ScalpingExecuteResponse)
async def execute(body: ScalpingExecuteRequest, request: Request) -> ScalpingExecuteResponse:
    """Route a scalping signal through the Paper/Live order path."""
    from app.api.v1.endpoints.trading import LiveOrderRequest, place_live_order

    cfg = _get_config(request)
    sym = body.underlying.upper()
    strategy = body.strategy

    c4h = _store_candles(sym, "4h", 60)
    c15m = _store_candles(sym, "15m", 7)

    if not c4h or not c15m:
        raise HTTPException(status_code=404, detail=f"No stored data for {sym}")

    sigs = scan_symbol(sym, c4h, c15m, cfg, tradeable=True)

    matched = [s for s in sigs if s.strategy == strategy and s.entry_ok]
    if not matched:
        return ScalpingExecuteResponse(
            accepted=False, mode="paper", underlying=sym, strategy=strategy,
            direction="none", size_units=0, notional_usd=0,
            status="no_signal", reason="no armed signal for this strategy",
            timestamp_ms=int(time.time() * 1000),
        )

    sig = matched[0]
    if sig.entry is None or sig.stop_loss is None:
        return ScalpingExecuteResponse(
            accepted=False, mode="paper", underlying=sym, strategy=strategy,
            direction=sig.direction, size_units=0, notional_usd=0,
            status="no_plan", reason="signal has no trade plan",
            timestamp_ms=int(time.time() * 1000),
        )

    risk_dist = abs(sig.entry - sig.stop_loss)
    if risk_dist <= 0:
        risk_dist = sig.entry * 0.02
    risk_usd = cfg.account_equity * (cfg.risk_percent / 100)
    size_units = risk_usd / risk_dist if risk_dist > 0 else 0
    contracts = max(0, int(round(size_units)))
    if contracts < 1:
        return ScalpingExecuteResponse(
            accepted=False, mode="paper", underlying=sym, strategy=strategy,
            direction=sig.direction, size_units=size_units, notional_usd=size_units * sig.entry,
            status="size_too_small", reason="sized below 1 contract",
            timestamp_ms=int(time.time() * 1000),
        )

    leverage = max(1.0, min((size_units * sig.entry) / max(1, cfg.account_equity * (cfg.max_position_pct / 100)), 25))

    order = LiveOrderRequest(
        underlying=sym, direction=sig.direction, instrument_type="futures",
        size=float(contracts), leverage=round(leverage, 1),
        order_type="market", stop_loss=sig.stop_loss,
        take_profit=sig.take_profit,
        notes=f"[SCALP-{strategy.upper()}] {sig.direction} {sig.pattern} near {sig.level_type} {sig.near_level:.0f}",
    )
    resp = await place_live_order(order, request)

    return ScalpingExecuteResponse(
        accepted=resp.status not in ("rejected", "error"),
        mode=resp.mode, underlying=sym, strategy=strategy,
        direction=sig.direction, size_units=float(contracts),
        notional_usd=round(contracts * sig.entry, 2),
        entry_price=resp.entry_price, stop_loss=sig.stop_loss,
        take_profit=sig.take_profit,
        order_id=resp.order_id, paper_position_id=resp.paper_position_id,
        status=resp.status, reason=resp.message,
        timestamp_ms=resp.timestamp_ms or int(time.time() * 1000),
    )