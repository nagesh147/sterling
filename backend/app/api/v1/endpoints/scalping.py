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
import json
import logging
import time
from dataclasses import asdict
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("sterling.scalping")

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
                # Handle migration: if saved config has no profiles, fill with defaults
                if not cfg.profiles:
                    cfg.profiles = default_config().profiles
            except Exception:
                cfg = default_config()
        else:
            cfg = default_config()
        request.app.state.scalping_config = cfg
    return cfg


def _get_optimized_params() -> dict:
    """The persisted optimizer-found parameter set (empty if never run)."""
    from app.services.db import get_config as _gc
    raw = _gc("scalping_optimized_params")
    if not raw:
        return {}
    try:
        return json.loads(raw) or {}
    except Exception:
        return {}


def _effective_config(request: Request) -> ScalpingConfig:
    """Manual config, with the optimizer's parameter set overlaid on a COPY when the
    `use_optimized` toggle is on. The stored manual config is never mutated — toggle
    off ⇒ this returns the manual config unchanged."""
    cfg = _get_config(request)
    if not getattr(cfg, "use_optimized", False):
        return cfg
    params = _get_optimized_params()
    if not params:
        return cfg
    # Only overlay keys that exist on the config (defensive against stale results).
    valid = {k: v for k, v in params.items() if k in ScalpingConfig.model_fields}
    return cfg.model_copy(update=valid) if valid else cfg


@router.get("/config", response_model=ScalpingConfigResponse)
async def get_config(request: Request) -> ScalpingConfigResponse:
    return ScalpingConfigResponse(config=_get_config(request))


@router.get("/config/default", response_model=ScalpingConfigResponse)
async def get_default_config() -> ScalpingConfigResponse:
    """Factory defaults (powers the 'Reset to defaults' button) — 4h/30m, PA+SMC+MA
    on, 1% risk, etc. Does not change live config; the UI sets the draft from this."""
    return ScalpingConfigResponse(config=default_config())


@router.post("/config", response_model=ScalpingConfigResponse)
async def set_config(body: ScalpingConfig, request: Request) -> ScalpingConfigResponse:
    from app.services.db import set_config as _sc
    request.app.state.scalping_config = body
    _sc("scalping_config", body.model_dump_json())
    return ScalpingConfigResponse(config=body)


@router.get("/presets")
async def presets() -> dict:
    """Named timeframe bundles (2y-OOS-grounded). The UI applies one by setting
    macro/execution TF + confirm bars on the config draft, then Save."""
    from app.engines.scalping.config import TIMEFRAME_PRESETS
    return {k: v.model_dump() for k, v in TIMEFRAME_PRESETS.items()}


@router.get("/universe", response_model=ScalpingUniverseResponse)
async def universe(request: Request) -> ScalpingUniverseResponse:
    """Symbols with enough 4H + 15min stored history."""
    cfg = _get_config(request)
    # Since profiles are independent, we'll use a conservative default min_bars
    min_bars = 200
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


_BARS_PER_DAY = {"5m": 288, "15m": 96, "30m": 48, "1h": 24, "2h": 12, "4h": 6}


def _bpd(tf: str) -> int:
    return _BARS_PER_DAY.get(tf, 24)


def _load_candles_by_res(syms: List[str], resolutions: set, days: int = 30) -> dict:
    """Load candles for multiple symbols and resolutions."""
    candles_by_res = {res: {} for res in resolutions}
    for sym in syms:
        for res in resolutions:
            extra = 60 if res in ("2h", "4h") else 20
            arr = _store_candles(sym, res, days + extra)
            if arr:
                candles_by_res[res][sym] = arr
    return candles_by_res


def _store_candles(sym: str, resolution: str, lookback_days: int):
    """Load candles from the local OHLCV store."""
    from app.services import ohlcv_store
    from app.schemas.market import Candle
    per_day = _BARS_PER_DAY.get(resolution, 24)
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
    tradeable_set: set = set()

    resolutions = set()
    for profile_id in cfg.active_profiles:
        p = cfg.profiles.get(profile_id)
        if p:
            resolutions.add(p.macro_timeframe or "4h")
            resolutions.add(p.execution_timeframe or "15m")

    candles_by_res = _load_candles_by_res(syms, resolutions, days=30)

    for sym in syms:
        try:
            inst = registry.get_instrument(sym)
            if inst and _adapter_can_serve(inst, src):
                tradeable_set.add(sym)
        except Exception:
            continue

    result = scan_universe(syms, candles_by_res, cfg, tradeable_set)
    return result


@router.get("/signals", response_model=ScalpingScanResponse)
async def signals(request: Request, armed_only: bool = False) -> ScalpingScanResponse:
    """Scan the stored-crypto universe, return signals from all enabled strategies."""
    import time as _t
    cfg = _effective_config(request)   # overlays optimized params when the toggle is on
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

    resolutions = set()
    for profile_id in cfg.active_profiles:
        p = cfg.profiles.get(profile_id)
        if p:
            resolutions.add(p.macro_timeframe or "4h")
            resolutions.add(p.execution_timeframe or "15m")
            
    candles_by_res = _load_candles_by_res([sym], resolutions, days=body.lookback_days)
    tradeable = bool(registry.get_instrument(sym))
    strategies = body.strategies or ["price_action", "smc", "ma_crossover"]

    all_trades: List[ScalpingBacktestTrade] = []
    
    # We only backtest the first active profile for now to avoid overlapping trades in the UI
    if cfg.active_profiles:
        profile_id = cfg.active_profiles[0]
        strat_cfg = cfg.profiles.get(profile_id)
        if strat_cfg:
            c_macro = candles_by_res.get(strat_cfg.macro_timeframe or "4h", {}).get(sym, [])
            c_exec = candles_by_res.get(strat_cfg.execution_timeframe or "15m", {}).get(sym, [])
            if not c_macro or not c_exec:
                raise HTTPException(status_code=404, detail=f"No stored data for {sym}")
                
            for strat in strategies:
                strat_copy = strat_cfg.model_copy(update={
                    "enable_price_action": strat == "price_action" and strat_cfg.enable_price_action,
                    "enable_smc": strat == "smc" and strat_cfg.enable_smc,
                    "enable_ma_crossover": strat == "ma_crossover" and strat_cfg.enable_ma_crossover,
                })
                sigs = scan_symbol(sym, c_macro, c_exec, strat_copy, profile_name=profile_id, tradeable=tradeable)
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
    from app.services import paper_store

    cfg = _effective_config(request)   # execute with optimized params when the toggle is on
    sym = body.underlying.upper()
    strategy = body.strategy

    # ── Which book will this order route to? ───────────────────────────
    # Mirror place_live_order's gate: a real (live) order is placed ONLY when
    # router_mode == "live" AND the active exchange has usable live credentials
    # and isn't itself in paper. Everything else (paper / shadow / live-without-
    # creds) lands in the paper book. The idempotency guard below must be scoped
    # to the SAME book, otherwise an open PAPER position silently blocks a LIVE
    # order for the same setup (the guard returns "already_open / paper" and no
    # live order is ever placed) — which is why live mode never mirrored paper.
    from app.services import exchange_account_store
    router_mode = (getattr(request.app.state, "algo_router_mode", "live") or "live").lower()
    _active = exchange_account_store.get_active()
    is_live_order = (
        router_mode == "live"
        and _active is not None
        and _active.name in ("delta_india", "delta")
        and bool(_active.api_key) and bool(_active.api_secret)
        and not _active.api_key.startswith("DUMMY")
        and not _active.is_paper
    )
    want_paper = not is_live_order

    # ── Idempotency guard (scoped to the target book) ──────────────────
    # Never stack a second open position on the same symbol+strategy WITHIN the
    # same book. Without this, any client re-fire (tab remount, mode switch, 30s
    # rescan) created a brand-new position — which is how hundreds of duplicate
    # paper positions accumulated. A paper and a live position for the same setup
    # are legitimate (different books), so the is_paper match keeps them separate.
    strat_tag = f"[SCALP-{strategy.upper()}]"
    existing = next(
        (p for p in paper_store.list_positions()
         if p.status.value in ("open", "partially_closed")
         and p.underlying == sym
         and strat_tag in (p.notes or "")
         and p.is_paper == want_paper),
        None,
    )
    if existing is not None:
        logger.info(
            "scalp-exec %s/%s router=%s want_paper=%s -> ALREADY_OPEN (%s position #%s) — not re-placed",
            sym, strategy, router_mode, want_paper,
            "paper" if existing.is_paper else "live", existing.id,
        )
        return ScalpingExecuteResponse(
            accepted=True,
            mode="paper" if existing.is_paper else "live",
            underlying=sym, strategy=strategy,
            direction=existing.sized_trade.structure.direction.value if existing.sized_trade else "none",
            size_units=float(getattr(existing.sized_trade, "contracts", 0) or 0),
            notional_usd=round(float(getattr(existing.sized_trade, "position_value", 0) or 0), 2),
            entry_price=existing.entry_spot_price,
            stop_loss=existing.initial_sl, take_profit=existing.initial_tp,
            paper_position_id=existing.id, order_id=existing.order_id,
            status="already_open",
            reason="An open position for this setup already exists — not duplicated.",
            timestamp_ms=int(time.time() * 1000),
        )

    resolutions = set()
    for profile_id in cfg.active_profiles:
        p = cfg.profiles.get(profile_id)
        if p:
            resolutions.add(p.macro_timeframe or "4h")
            resolutions.add(p.execution_timeframe or "15m")
            
    candles_by_res = _load_candles_by_res([sym], resolutions, days=30)

    # Scan to find the armed signal across active profiles
    from app.engines.scalping.scanner import scan_universe
    scan_resp = scan_universe([sym], candles_by_res, cfg, tradeable_set={sym})
    sigs = scan_resp.signals

    matched = [s for s in sigs if s.strategy == strategy and s.entry_ok]
    if not matched:
        logger.info("scalp-exec %s/%s -> no_signal (not armed at execute time)", sym, strategy)
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
        logger.info("scalp-exec %s/%s -> size_too_small (%.4f units, equity=%s risk%%=%s)",
                    sym, strategy, size_units, cfg.account_equity, cfg.risk_percent)
        return ScalpingExecuteResponse(
            accepted=False, mode="paper", underlying=sym, strategy=strategy,
            direction=sig.direction, size_units=size_units, notional_usd=size_units * sig.entry,
            status="size_too_small", reason="sized below 1 contract",
            timestamp_ms=int(time.time() * 1000),
        )

    leverage = max(1.0, min((size_units * sig.entry) / max(1, cfg.account_equity * (cfg.max_position_pct / 100)), 25))

    # Tag the placer (algo auto-exec vs manual click) into the notes so the UI can
    # consistently show "AUTO · <MODE>" on every reconstructed row, not just the
    # one you just clicked. The [SCALP-...] tag stays intact for strategy parsing.
    auto_tag = " [AUTO]" if body.auto else ""
    order = LiveOrderRequest(
        underlying=sym, direction=sig.direction, instrument_type="futures",
        size=float(contracts), leverage=round(leverage, 1),
        order_type="market", stop_loss=sig.stop_loss,
        take_profit=sig.take_profit,
        notes=f"[SCALP-{strategy.upper()}]{auto_tag} {sig.direction} {sig.pattern} near {sig.level_type} {sig.near_level:.0f}",
    )
    resp = await place_live_order(order, request)

    logger.info(
        "scalp-exec %s/%s router=%s want_live=%s -> mode=%s status=%s order_id=%s entry=%s sl=%s tp=%s contracts=%s reason=%s",
        sym, strategy, router_mode, is_live_order, resp.mode, resp.status,
        resp.order_id, resp.entry_price, sig.stop_loss, sig.take_profit, contracts, resp.message,
    )

    # Trigger all active webhooks (Discord, Telegram, Zapier)
    if resp.status not in ("rejected", "error"):
        from app.services import webhook_store
        asyncio.create_task(
            webhook_store.deliver_all(
                subject=f"SCALP EXECUTE ({resp.mode.upper()}) — {sym} {sig.direction.upper()}",
                message=f"Strategy: {strategy}\nOrder Status: {resp.status}\nContracts: {contracts}\nEntry: {sig.entry}\nSL: {sig.stop_loss}\nTP: {sig.take_profit}",
                data={
                    "mode": resp.mode,
                    "underlying": sym,
                    "direction": sig.direction,
                    "strategy": strategy,
                    "contracts": contracts,
                    "entry_price": sig.entry,
                    "stop_loss": sig.stop_loss,
                    "take_profit": sig.take_profit,
                    "status": resp.status,
                    "notional_usd": round(contracts * sig.entry, 2),
                }
            )
        )

    return ScalpingExecuteResponse(
        accepted=resp.status not in ("rejected", "error"),
        mode=resp.mode, underlying=sym, strategy=strategy,
        direction=sig.direction, size_units=float(contracts),
        notional_usd=round(contracts * sig.entry, 2),
        entry_price=resp.entry_price, stop_loss=sig.stop_loss,
        take_profit=sig.take_profit,
        tp_source=getattr(sig, 'tp_source', ''),
        order_id=resp.order_id, paper_position_id=resp.paper_position_id,
        status=resp.status, reason=resp.message,
        timestamp_ms=resp.timestamp_ms or int(time.time() * 1000),
        telegram_alert_sent=resp.status not in ("rejected", "error"),
    )


# ─── optimize (focused, OOS-robust parameter sweep) ──────────────────────────

# Default sweep universe — liquid majors; filtered to what actually has data.
_OPT_UNIVERSE = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "AVAX", "LINK", "LTC"]

_optimize_state: dict = {
    "running": False, "progress": "", "started_ms": 0, "done_ms": 0, "error": None,
}


async def _run_optimize(base_cfg: ScalpingConfig, days: int, max_symbols: int) -> None:
    """Background worker: load candles per resolution, run the TF×param sweep
    off-thread, persist results."""
    from app.engines.scalping.optimizer import optimize as _optimize, DEFAULT_TF_PAIRS
    from app.services.db import set_config as _sc

    _optimize_state.update(running=True, progress="loading", started_ms=int(time.time() * 1000),
                           done_ms=0, error=None)
    try:
        # every resolution referenced by the TF grid (+ the manual config's own TFs)
        resolutions = {base_cfg.macro_timeframe or "4h", base_cfg.execution_timeframe or "15m"}
        for m, e in DEFAULT_TF_PAIRS:
            resolutions.add(m); resolutions.add(e)

        syms = [s.upper() for s in base_cfg.symbols] or _OPT_UNIVERSE
        candles_by_res: dict = {res: {} for res in resolutions}
        chosen = 0
        for s in syms:
            if chosen >= max_symbols:
                break
            loaded, ok = {}, True
            for res in resolutions:
                extra = 60 if res in ("2h", "4h") else 20
                arr = _store_candles(s, res, days + extra)
                if len(arr) < 250:                 # need enough bars for the finest TF
                    ok = False; break
                loaded[res] = arr
            if ok:
                chosen += 1
                for res in resolutions:
                    candles_by_res[res][s] = loaded[res]
        if not chosen:
            _optimize_state.update(running=False, error="no stored data with all required timeframes",
                                   done_ms=int(time.time() * 1000))
            return

        def _prog(n: int, total: int) -> None:
            _optimize_state["progress"] = f"{n}/{total}"

        result = await asyncio.to_thread(_optimize, candles_by_res, base_cfg, None, None, _prog)
        _sc("scalping_optimize_result", json.dumps(asdict(result)))
        _sc("scalping_optimized_params", json.dumps(result.best_params))
        logger.info("scalp-optimize done: best=%s OOS-corr=%s universe=%s",
                    result.best_params, result.is_oos_corr, result.universe)
        _optimize_state.update(running=False, progress=f"{result.n_combos}/{result.n_combos}",
                               done_ms=int(time.time() * 1000))
    except Exception as exc:                                  # pragma: no cover - background safety
        logger.warning("scalp-optimize failed: %s", exc)
        _optimize_state.update(running=False, error=str(exc), done_ms=int(time.time() * 1000))


@router.post("/optimize")
async def optimize_run(request: Request, days: int = 60, max_symbols: int = 4) -> dict:
    """Kick off a background OOS-robust timeframe×parameter sweep over the universe.

    Ranks the grid by held-out (out-of-sample) profit factor; persists the ranked
    results and the winning set. Does NOT change live behavior — enable the
    `use_optimized` toggle to trade the winning set. Defaults are modest because
    the TF sweep replays fine-grained (5m) data; raise days/max_symbols for a
    firmer verdict at the cost of a longer (several-minute) background run.
    """
    if _optimize_state["running"]:
        return {"status": "already_running", **_optimize_state}
    days = max(30, min(int(days), 365))
    max_symbols = max(2, min(int(max_symbols), 10))
    base_cfg = _get_config(request)                          # manual config = the sweep's base
    asyncio.create_task(_run_optimize(base_cfg, days, max_symbols))
    return {"status": "started", "days": days, "max_symbols": max_symbols}


@router.get("/optimize")
async def optimize_get() -> dict:
    """Current sweep status + last ranked results + the persisted winning params."""
    from app.services.db import get_config as _gc
    raw = _gc("scalping_optimize_result")
    result = None
    if raw:
        try:
            result = json.loads(raw)
        except Exception:
            result = None
    return {
        "status": dict(_optimize_state),
        "result": result,
        "optimized_params": _get_optimized_params() or None,
    }