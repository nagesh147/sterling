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

from app.engines.sterling_engine.config import ScalpingConfig, default_config
from app.engines.sterling_engine.schemas import (
    ScalpingScanResponse, ScalpingConfigResponse, ScalpingUniverseResponse,
    ScalpingSignal, ScalpingBacktestRequest, ScalpingBacktestResult,
    ScalpingBacktestTrade, ScalpingExecuteRequest, ScalpingExecuteResponse,
)
router = APIRouter(prefix="/sterling-engine", tags=["sterling_engine"])


def _contracts_from_units(size_units: float, contract_value: float) -> int:
    """Convert a coin-denominated position (size_units, in whole coins) into the
    number of whole EXCHANGE lots. `contract_value` is the size of one lot in the
    underlying (Delta India perps: BTC=0.001, ETH=0.01, SOL=1). A 0.42 ETH target
    is 0.42 / 0.01 = 42 lots — the old `int(round(size_units))` floored it to 0 and
    rejected the trade. Returns 0 when the position is below one whole lot."""
    cv = contract_value if contract_value and contract_value > 0 else 1.0
    return max(0, int(round(size_units / cv)))


# ─── config ────────────────────────────────────────────────────────────────


def _get_config(request: Request) -> ScalpingConfig:
    cfg = getattr(request.app.state, "sterling_engine_config", None)
    if cfg is None:
        from app.services.db import get_config as _gc
        # New key, falling back to the legacy "scalping_config" for pre-rename installs.
        saved = _gc("sterling_engine_config") or _gc("scalping_config")
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
        request.app.state.sterling_engine_config = cfg
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


def _reentry_cooldown_remaining_min(
    positions, *, sym: str, strat_tag: str, want_paper: bool,
    direction: str, cooldown_min: float, now_ms: int,
) -> float:
    """Minutes left before the algo may re-enter this exact setup
    (symbol + strategy + direction + book). 0.0 = clear to enter.

    Looks at the most recent CLOSED matching position's exit time. Stops the
    rapid sequential re-entry that churned the same 4H level (e.g. the May-30
    cluster of ETH 'overbought' shorts, each a small loss). Manual clicks are
    exempt (the caller only applies this to auto-exec).
    """
    if cooldown_min <= 0:
        return 0.0
    last_exit = 0
    for p in positions:
        if getattr(p, "underlying", None) != sym:
            continue
        if strat_tag not in (getattr(p, "notes", "") or ""):
            continue
        if getattr(p, "is_paper", None) != want_paper:
            continue
        if getattr(getattr(p, "status", None), "value", None) != "closed":
            continue
        st = getattr(p, "sized_trade", None)
        pdir = getattr(getattr(getattr(st, "structure", None), "direction", None), "value", None)
        if pdir != direction:
            continue
        last_exit = max(last_exit, int(getattr(p, "exit_timestamp_ms", 0) or 0))
    if not last_exit:
        return 0.0
    remaining_ms = cooldown_min * 60_000 - (now_ms - last_exit)
    return max(0.0, remaining_ms / 60_000)


def _effective_config(request: Request) -> ScalpingConfig:
    """Manual config, with the institutional WFO parameters overlaid on a COPY when the
    `use_optimized` toggle (AI Gatekeeper) is on. The stored manual config is never mutated."""
    cfg = _get_config(request)
    if not getattr(cfg, "use_optimized", False):
        return cfg
    
    # WFO Active: mathematically enforce the Edge Whitelist!
    # We overlay the verified profiles and active_profiles, but preserve the user's symbols, 
    # risk rules, and global settings.
    wfo = default_config()
    
    merged_profiles = {}
    for pid, wfo_prof in wfo.profiles.items():
        user_prof = cfg.profiles.get(pid)
        if user_prof:
            merged_prof = wfo_prof.model_copy(update={
                "account_equity": user_prof.account_equity,
                "risk_percent": user_prof.risk_percent,
                "max_position_pct": user_prof.max_position_pct,
                "allow_long": user_prof.allow_long,
                "allow_short": user_prof.allow_short,
                "min_rr": user_prof.min_rr,
                "max_stop_atr": user_prof.max_stop_atr,
                "macro_trend_filter": user_prof.macro_trend_filter,
            })
            merged_profiles[pid] = merged_prof
        else:
            merged_profiles[pid] = wfo_prof

    return cfg.model_copy(update={
        "active_profiles": wfo.active_profiles,
        "profiles": merged_profiles,
        "tiered_tp": wfo.tiered_tp,
    })


@router.get("/config", response_model=ScalpingConfigResponse)
async def get_config(request: Request) -> ScalpingConfigResponse:
    return ScalpingConfigResponse(config=_effective_config(request))


@router.get("/config/default", response_model=ScalpingConfigResponse)
async def get_default_config() -> ScalpingConfigResponse:
    """Factory defaults (powers the 'Reset to defaults' button) — 4h/30m, PA+SMC+MA
    on, 1% risk, etc. Does not change live config; the UI sets the draft from this."""
    return ScalpingConfigResponse(config=default_config())


@router.post("/config", response_model=ScalpingConfigResponse)
async def set_config(body: ScalpingConfig, request: Request) -> ScalpingConfigResponse:
    from app.services.db import set_config as _sc
    request.app.state.sterling_engine_config = body
    _sc("sterling_engine_config", body.model_dump_json())
    return ScalpingConfigResponse(config=_effective_config(request))


@router.get("/presets")
async def presets() -> dict:
    """Named timeframe bundles (2y-OOS-grounded). The UI applies one by setting
    macro/execution TF + confirm bars on the config draft, then Save."""
    from app.engines.sterling_engine.config import TIMEFRAME_PRESETS
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


_BARS_PER_DAY = {"5m": 288, "15m": 96, "30m": 48, "1h": 24, "2h": 12, "4h": 6, "1d": 1}

# Macro TFs the candle fetcher doesn't store natively are rebuilt by resampling
# the nearest finer resolution that IS stored. The swing_4h profile uses a 1d
# macro, but the fetcher only keeps {5m..4h}; without this the profile is silently
# dead (no daily candles → no levels → no signals). Maps target -> (source, bucket_secs).
_RESAMPLE_FROM = {"1d": ("4h", 86_400)}


def _bpd(tf: str) -> int:
    return _BARS_PER_DAY.get(tf, 24)


def _resample_candles(candles: list, bucket_secs: int) -> list:
    """Aggregate finer candles into fixed UTC-aligned OHLCV buckets.
    `candles` must be ascending by timestamp; the epoch grid keeps daily buckets
    aligned to 00:00 UTC, matching exchange daily bars."""
    from app.schemas.market import Candle
    out: list = []
    cur = None
    o = h = l = c = v = 0.0
    for cd in candles:
        b = (cd.timestamp_ms // 1000) // bucket_secs * bucket_secs
        if cur is None or b != cur:
            if cur is not None:
                out.append(Candle(timestamp_ms=cur * 1000, open=o, high=h, low=l, close=c, volume=v))
            cur, o, h, l, c, v = b, cd.open, cd.high, cd.low, cd.close, cd.volume
        else:
            h = max(h, cd.high); l = min(l, cd.low); c = cd.close; v += cd.volume
    if cur is not None:
        out.append(Candle(timestamp_ms=cur * 1000, open=o, high=h, low=l, close=c, volume=v))
    return out


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
    """Load candles from the local OHLCV store. Macro resolutions the fetcher does
    not keep natively (e.g. 1d for the swing_4h profile) are resampled from a stored
    finer resolution so the profile isn't silently starved of data."""
    from app.services import ohlcv_store
    from app.schemas.market import Candle
    per_day = _BARS_PER_DAY.get(resolution, 24)
    limit = min(lookback_days * per_day + 300, 40_000)
    since = int(time.time()) - lookback_days * 86_400
    rows = ohlcv_store.get_candles(f"{sym}USD", resolution, limit=limit, since=since)
    candles = [
        Candle(
            timestamp_ms=int(r["time"]) * 1000,
            open=r["open"], high=r["high"], low=r["low"],
            close=r["close"], volume=r["volume"],
        )
        for r in rows
    ]
    if len(candles) < 2 and resolution in _RESAMPLE_FROM:
        src_res, bucket = _RESAMPLE_FROM[resolution]
        candles = _resample_candles(_store_candles(sym, src_res, lookback_days), bucket)
    return candles


# ─── signals (multi-symbol scan) ──────────────────────────────────────────


_SCAN_TTL = 120.0
_scan_cache: dict = {"key": None, "ts": 0.0, "data": None}
_scan_lock = asyncio.Lock()


def _scan_all(cfg: ScalpingConfig, src: str) -> ScalpingScanResponse:
    """Evaluate the full universe across all enabled strategies."""
    from app.engines.sterling_engine.scanner import scan_universe
    import numpy as np
    from app.engines.sterling_engine.levels import detect_levels

    syms = [s.upper() for s in cfg.symbols] if cfg.symbols else _store_symbols(
        min_bars_hours=max(cfg.warmup_bars_4h, cfg.warmup_bars_15m // 4 + 20)
    )

    # Skip disabled symbols (core toggle on/off without removing)
    disabled = {s.upper() for s in (cfg.disabled_symbols or [])}
    syms = [s for s in syms if s not in disabled]

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
    """Honest bar-by-bar replay of the scalping strategies on stored data.

    Replays each enabled strategy with real SL/TP exits and real costs (fee +
    slippage + funding), then reports sample-size adequacy, regime coverage,
    and a 70/30 in-sample/out-of-sample split so a single run shows whether the
    edge is real or curve-fit. See `engines.sterling_engine.backtest`.
    """
    from app.engines.sterling_engine.backtest import run_scalping_backtest
    from app.engines.sterling_engine.schemas import (
        SampleQuality, RegimeCoverage, OOSSplit,
    )

    cfg = body.config or _get_config(request)
    sym = body.underlying.upper()

    if not cfg.active_profiles:
        raise HTTPException(status_code=400, detail="No active scalping profile configured")
    profile_id = cfg.active_profiles[0]   # one profile to avoid overlapping trades in the UI
    strat_cfg = cfg.profiles.get(profile_id)
    if not strat_cfg:
        raise HTTPException(status_code=400, detail=f"Active profile '{profile_id}' not found")

    macro_tf = strat_cfg.macro_timeframe or "4h"
    exec_tf = strat_cfg.execution_timeframe or "15m"
    candles_by_res = _load_candles_by_res([sym], {macro_tf, exec_tf}, days=body.lookback_days)
    c_macro = candles_by_res.get(macro_tf, {}).get(sym, [])
    c_exec = candles_by_res.get(exec_tf, {}).get(sym, [])
    if not c_macro or not c_exec:
        raise HTTPException(status_code=404, detail=f"No stored {macro_tf}/{exec_tf} data for {sym}")

    strategies = body.strategies or list(
        s for s in ("price_action", "smc", "ma_crossover", "mean_reversion", "breakout")
        if getattr(strat_cfg, f"enable_{s}", False)
    )

    out = await asyncio.to_thread(
        run_scalping_backtest, sym, c_macro, c_exec, strat_cfg, strategies,
    )

    return ScalpingBacktestResult(
        underlying=sym, lookback_days=body.lookback_days,
        bars_evaluated=out.bars_evaluated, config=cfg,
        trades=[
            ScalpingBacktestTrade(
                direction=t.direction, strategy=t.strategy,
                entry_ts=t.entry_ts, exit_ts=t.exit_ts,
                entry_price=t.entry_price, exit_price=t.exit_price,
                bars_held=t.bars_held, pnl_r=round(t.pnl_r, 2),
                gross_pnl_r=round(t.gross_pnl_r, 2),
                exit_reason=t.exit_reason, regime=t.regime,
            )
            for t in out.trades
        ],
        total_trades=out.total_trades,
        win_rate=round(out.win_rate, 3),
        total_return_pct=out.net_return_pct,
        max_drawdown_pct=out.max_drawdown_pct,
        expectancy_r=out.expectancy_r,
        profit_factor=out.profit_factor,
        avg_cost_r=out.avg_cost_r,
        cost_modeled=True,
        equity_curve=out.equity_curve,
        sample_quality=SampleQuality(**out.sample_quality),
        regime_coverage=RegimeCoverage(**out.regime_coverage),
        oos=OOSSplit(**out.oos),
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

    # Try the cached scan result first — this is what the UI displayed when the
    # user clicked execute. A fresh re-scan can lose signals (regime shift,
    # macro_trend_filter, candle data change) between the periodic scan and
    # this execute call, causing "no_signal" on a setup the user literally
    # clicked on. Cache → fresh fallback ensures the clicked signal is found.
    matched = []
    cached: ScalpingScanResponse | None = _scan_cache.get("data")
    if cached and cached.signals:
        matched = [s for s in cached.signals
                    if s.underlying == sym and s.strategy == strategy
                    and (s.entry_ok or body.confirm)]

    if not matched:
        resolutions = set()
        for profile_id in cfg.active_profiles:
            p = cfg.profiles.get(profile_id)
            if p:
                resolutions.add(p.macro_timeframe or "4h")
                resolutions.add(p.execution_timeframe or "15m")
        candles_by_res = _load_candles_by_res([sym], resolutions, days=30)
        from app.engines.sterling_engine.scanner import scan_universe
        scan_resp = scan_universe([sym], candles_by_res, cfg, tradeable_set={sym})
        sigs = scan_resp.signals
        matched = [s for s in sigs if s.strategy == strategy and (s.entry_ok or body.confirm)]

    if not matched:
        logger.info("scalp-exec %s/%s -> no_signal (not armed at execute time)", sym, strategy)
        return ScalpingExecuteResponse(
            accepted=False, mode="paper", underlying=sym, strategy=strategy,
            direction="none", size_units=0, notional_usd=0,
            status="no_signal", reason="No signal was ready to trade for this strategy at execution time.",
            timestamp_ms=int(time.time() * 1000),
        )

    sig = matched[0]
    if body.override_entry is not None:
        sig.entry = body.override_entry
    if body.override_stop is not None:
        sig.stop_loss = body.override_stop
    if sig.entry is None or sig.stop_loss is None:
        return ScalpingExecuteResponse(
            accepted=False, mode="paper", underlying=sym, strategy=strategy,
            direction=sig.direction, size_units=0, notional_usd=0,
            status="no_plan", reason="signal has no trade plan",
            timestamp_ms=int(time.time() * 1000),
        )

    profile_id = getattr(sig, "profile", "") or (cfg.active_profiles[0] if cfg.active_profiles else "intraday")
    strat_cfg = cfg.profiles.get(profile_id)
    if not strat_cfg:
        return ScalpingExecuteResponse(
            accepted=False, mode="paper", underlying=sym, strategy=strategy,
            direction=sig.direction, size_units=0, notional_usd=0,
            status="error", reason=f"Profile '{profile_id}' not found",
            timestamp_ms=int(time.time() * 1000),
        )

    # ── Re-entry cooldown (auto-exec only) ─────────────────────────────
    # Manual clicks are exempt; the algo must wait after closing this exact
    # setup so it can't churn one 4H level into a pile of small losses.
    if body.auto:
        _cd_left = _reentry_cooldown_remaining_min(
            paper_store.list_positions(), sym=sym, strat_tag=strat_tag,
            want_paper=want_paper, direction=sig.direction,
            cooldown_min=getattr(strat_cfg, "reentry_cooldown_min", 45),
            now_ms=int(time.time() * 1000),
        )
        if _cd_left > 0:
            logger.info("scalp-exec %s/%s %s -> COOLDOWN (%.0fmin left) — not re-entered",
                        sym, strategy, sig.direction, _cd_left)
            return ScalpingExecuteResponse(
                accepted=False, mode="paper" if want_paper else "live",
                underlying=sym, strategy=strategy, direction=sig.direction,
                size_units=0, notional_usd=0, status="cooldown",
                reason=(f"{strategy} {sig.direction} {sym} in re-entry cooldown "
                        f"— {_cd_left:.0f} min left after the last exit."),
                timestamp_ms=int(time.time() * 1000),
            )

    # Exchange lot size for this perp — converts the coin-sized target into whole
    # exchange lots (Delta India: ETH=0.01, BTC=0.001, SOL=1). Falls back to 1.0
    # (coin == lot) when the adapter can't supply it, so sizing never mis-fires.
    contract_value = 1.0
    try:
        # Use the RAW adapter — the CachingAdapter/RetryingAdapter wrappers from
        # get_adapter() only proxy a fixed method list and don't expose
        # get_contract_value (nor get_product_id). app.state.adapter is a raw
        # fallback that's only populated when the user switches exchanges.
        _ad = _adm.get_raw_adapter() or getattr(request.app.state, "adapter", None)
        _get_cv = getattr(_ad, "get_contract_value", None)
        if _get_cv is not None:
            _inst = registry.get_instrument(sym)
            _delta_sym = (_inst.delta_perp_symbol if _inst else None) or f"{sym}USD"
            contract_value = float(await _get_cv(_delta_sym)) or 1.0
    except Exception as _cv_exc:
        logger.debug("scalp-exec %s: contract_value lookup failed (%s) — using 1.0", sym, _cv_exc)

    risk_dist = abs(sig.entry - sig.stop_loss)
    if risk_dist <= 0:
        risk_dist = sig.entry * 0.02
    risk_usd = strat_cfg.account_equity * (strat_cfg.risk_percent / 100)
    size_units = risk_usd / risk_dist if risk_dist > 0 else 0   # target coin quantity
    contracts = _contracts_from_units(size_units, contract_value)  # whole exchange lots
    qty = contracts * contract_value                              # coins actually placed
    if contracts < 1:
        logger.info("scalp-exec %s/%s -> size_too_small (%.4f coins / cv=%s = %.3f lots, equity=%s risk%%=%s)",
                    sym, strategy, size_units, contract_value, size_units / (contract_value or 1.0),
                    strat_cfg.account_equity, strat_cfg.risk_percent)
        return ScalpingExecuteResponse(
            accepted=False, mode="paper", underlying=sym, strategy=strategy,
            direction=sig.direction, size_units=size_units, notional_usd=size_units * sig.entry,
            status="size_too_small", reason="sized below one exchange lot",
            timestamp_ms=int(time.time() * 1000),
        )

    leverage = max(1.0, min((qty * sig.entry) / max(1, strat_cfg.account_equity * (strat_cfg.max_position_pct / 100)), 25))

    # Tag the placer (algo auto-exec vs manual click) into the notes so the UI can
    # consistently show "AUTO · <MODE>" on every reconstructed row, not just the
    # one you just clicked. The [SCALP-...] tag stays intact for strategy parsing.
    auto_tag = " [AUTO]" if body.auto else ""
    level_str = f" near {sig.level_type} {sig.near_level:.0f}" if sig.near_level is not None else ""

    # ── Phase 5: route through DerivativesSelector when its profile is on ──
    # Profile.enabled defaults to False on first install so the legacy
    # futures path runs unchanged. Operator flips the per-strategy profile
    # on via /derivatives/config after live observation. Selector
    # PROFILE_OFF / FAIL_OPEN / DEFER all fall through to the legacy path
    # so a selector hiccup never blocks the order.
    selector_route_used = False
    selector_audit_id: str | None = None
    selector_inst_type = "futures"
    selector_size = float(contracts)
    selector_leverage = round(leverage, 1)
    selector_sl = sig.stop_loss
    selector_tp = sig.take_profit
    selector_option_symbol: str | None = None

    try:
        from app.engines.derivatives.selector import decide as _sel_decide
        from app.engines.derivatives.schemas import (
            SignalContext as _SigCtx, MarketContext as _MktCtx, DecisionStatus as _DS,
        )
        from app.services import derivatives_audit as _audit
        from app.services.exchanges import instrument_registry as _reg
        overrides = getattr(request.app.state, "derivatives_profile_overrides", None) or {}

        ad = request.app.state.adapter
        inst = _reg.get_instrument(sym)
        spot = float(await ad.get_index_price(inst)) if inst else float(sig.entry)
        try:
            pid = await ad.get_product_id(inst.delta_perp_symbol or f"{sym}USD") if inst else None
            funding_8h = float((await ad.get_funding_rate(pid)).get("funding_rate_8h_pct") or 0.0001) if pid else 0.0001
        except Exception:
            funding_8h = 0.0001
        cb = getattr(request.app.state, "dd_circuit_breaker", None)
        cb_mult = float(cb.size_multiplier()) if cb is not None else 1.0
        cal = getattr(request.app.state, "calibration_service", None)
        win_rate = cal.win_rate() if cal is not None else None
        chain = await ad.get_option_chain(inst) if (inst and getattr(inst, "has_options", False)) else None

        sig_ctx = _SigCtx(
            strategy=f"{profile_id}/{strategy}", underlying=sym, direction=sig.direction,
            entry=float(sig.entry), stop_loss=float(sig.stop_loss),
            take_profit=sig.take_profit, atr=0.0, rr_target=2.0,
            signal_score=50.0, signal_strength="STRONG",
            expected_hold_minutes=75, mode_name="sterling",
        )
        mkt_ctx = _MktCtx(
            spot=spot, underlying=sym, funding_8h_pct=funding_8h,
            cb_size_mult=cb_mult, win_rate=win_rate, avg_R=None,
            portfolio_value=float(strat_cfg.account_equity),
        )
        decision = _sel_decide(signal=sig_ctx, market=mkt_ctx, chain=chain,
                               profile_overrides=overrides)
        if decision.status == _DS.OK and decision.chosen is not None:
            c = decision.chosen
            selector_route_used = True
            selector_inst_type = c.instrument_type
            selector_size = float(c.contracts)
            selector_leverage = float(c.leverage)
            selector_sl = c.stop_loss
            selector_tp = c.take_profit
            selector_option_symbol = c.option_symbol
            selector_audit_id = _audit.record(decision=decision, signal=sig_ctx, market=mkt_ctx)
    except Exception as _sel_exc:
        logger.debug("scalp-exec selector path failed for %s: %s — using legacy futures", sym, _sel_exc)

    notes = f"[SCALP-{strategy.upper()}]{auto_tag} {sig.direction} {sig.pattern}{level_str}".strip()
    if selector_audit_id:
        notes += f" [DERIV-aid={selector_audit_id[:8]}]"

    # Legacy futures path sizes in exchange lots, so carry the lot size through to
    # the paper/live valuation. The selector path returns its OWN contract count
    # (options/futures with its own semantics) — keep cv=1.0 there, unchanged.
    order_contract_value = 1.0 if selector_route_used else contract_value
    # Coin quantity actually being placed = order size (lots) × lot size. Used for
    # honest notional reporting on both the legacy-futures and selector paths.
    report_qty = float(selector_size) * order_contract_value

    order = LiveOrderRequest(
        underlying=sym, direction=sig.direction, instrument_type=selector_inst_type,
        size=selector_size, contract_value=order_contract_value, leverage=selector_leverage,
        order_type="market", stop_loss=selector_sl, take_profit=selector_tp,
        option_symbol=selector_option_symbol,
        notes=notes,
        # Real account NAV so capital-at-risk reports a true % (not /$100k default).
        account_equity=strat_cfg.account_equity,
    )
    resp = await place_live_order(order, request)
    if selector_route_used and selector_audit_id and resp.status not in ("rejected", "error"):
        try:
            from app.services import derivatives_audit as _audit
            _audit.mark_executed(selector_audit_id)
        except Exception:
            pass

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
                    "notional_usd": round(report_qty * sig.entry, 2),
                }
            )
        )

    return ScalpingExecuteResponse(
        accepted=resp.status not in ("rejected", "error"),
        mode=resp.mode, underlying=sym, strategy=strategy,
        direction=sig.direction, size_units=round(report_qty, 6),
        notional_usd=round(report_qty * sig.entry, 2),
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
    from app.engines.sterling_engine.optimizer import optimize as _optimize, DEFAULT_TF_PAIRS
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