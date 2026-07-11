"""DerivativesSelector API surface.

Endpoints:
  GET  /derivatives/candidates       — table rows for the FE
  GET  /derivatives/preview          — full decision detail for one signal
  POST /derivatives/execute          — execute a frozen candidate
  GET  /derivatives/config           — per-strategy profile dict
  POST /derivatives/config           — patch profile(s)
  GET  /derivatives/greeks-budget    — portfolio Greeks state
  GET  /derivatives/funding/{ul}     — live funding read
  GET  /derivatives/book/{symbol}    — L2 book

Profiles live on `app.state.derivatives_profile_overrides` (a dict keyed
by strategy slug). Initialised lazily; never persisted (operator can
re-set on each session — restart is a clean slate by design).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from app.core.async_tasks import spawn_background

from app.engines.derivatives.freeze_token import get_store as get_freeze_store
from app.engines.derivatives.preview import preview_one
from app.engines.derivatives.profiles import DEFAULT_PROFILES, get_profile
from app.engines.derivatives.schemas import (
    DecisionStatus, DerivativesDecision,
    MarketContext, SignalContext, StrategyDerivativesProfile,
)
from app.engines.derivatives.selector import decide_both as _decide_both
from app.engines.derivatives_native import engine as _native_engine
from app.engines.derivatives_native.config import (
    DerivativesEngineConfig, EngineMode, get_engine_config, set_engine_config,
)
from app.engines.risk.option_pricing import enrich_chain
from app.services import derivatives_audit
from app.services.exchanges import instrument_registry as registry
from app.services import adapter_manager as _adm

router = APIRouter(prefix="/derivatives", tags=["derivatives"])
log = logging.getLogger(__name__)


# ─── helpers ───────────────────────────────────────────────────────────


def _profile_overrides(app) -> dict[str, StrategyDerivativesProfile]:
    cur = getattr(app.state, "derivatives_profile_overrides", None)
    if cur is None:
        # Seed with the defaults (still profile.enabled=False) so GET /config
        # shows the operator the full strategy slate even before any edit.
        cur = {k: v.model_copy() for k, v in DEFAULT_PROFILES.items()}
        app.state.derivatives_profile_overrides = cur
    return cur


def _spot_from_store(underlying: str):
    """Last stored close as a spot fallback when the live feed is cold, so a
    transient WS gap doesn't empty the candidate tables. Tries a few symbol forms."""
    try:
        from app.services import ohlcv_store
    except Exception:
        return None
    u = underlying.upper()
    for sym in (u, f"{u}USD", u.replace("USD", "")):
        for res in ("1h", "15m", "5m"):
            try:
                rows = ohlcv_store.get_candles(sym, res)
            except Exception:
                rows = None
            if rows:
                last = rows[-1]
                c = last.get("close") if isinstance(last, dict) else getattr(last, "close", None)
                if c:
                    return float(c)
    return None


async def _market_context(
    *, underlying: str, app, signal_score: float = 0.0,
) -> MarketContext:
    """Build a MarketContext from live adapter calls + calibration + CB.

    Spot is resilient: if the live adapter is cold / the WS feed has a gap, it
    falls back to the last stored candle close so the candidate tables don't
    silently empty on a transient feed hiccup."""
    adapter = _adm.get_adapter() or getattr(app.state, "adapter", None)
    inst = registry.get_instrument(underlying.upper()) or \
        registry.get_instrument(underlying.upper().replace("USD", ""))   # "BTCUSD" → "BTC"
    if inst is None:
        raise HTTPException(status_code=503, detail="instrument unavailable")

    spot = None
    if adapter is not None:
        try:
            spot = float(await adapter.get_index_price(inst))
        except Exception as exc:
            log.warning("DERIV spot fetch failed for %s: %s — falling back to candle store",
                        underlying, exc)
    if not spot or spot <= 0:
        spot = _spot_from_store(underlying)
    if not spot or spot <= 0:
        raise HTTPException(status_code=503,
                            detail="no spot available (adapter cold + no stored candles)")

    # Funding rate via the new adapter method
    funding_8h = 0.0001
    try:
        pid = await adapter.get_product_id(inst.delta_perp_symbol or f"{underlying.upper()}USD")
        fr = await adapter.get_funding_rate(pid)
        funding_8h = float(fr.get("funding_rate_8h_pct") or 0.0001)
    except Exception:
        pass

    # CB / regime / calibration consumers
    dd_cb = getattr(app.state, "dd_circuit_breaker", None)
    cb_mult = float(dd_cb.size_multiplier()) if dd_cb is not None else 1.0
    cal = getattr(app.state, "calibration_service", None)
    win_rate = None
    avg_r = None
    try:
        if cal is not None:
            win_rate = cal.win_rate()
    except Exception:
        win_rate = None

    portfolio_value = float(getattr(dd_cb, "peak", 100_000.0)) if dd_cb else 100_000.0

    # GEX profile — used by the native engine's gex_pinning alpha source
    gex_profile = None
    try:
        inst = registry.get_instrument(underlying.upper())
        if inst and getattr(inst, "has_options", False):
            chain = await adapter.get_option_chain(inst)
            if chain:
                from app.engines.derivatives.gex_engine import calculate_gex_profile
                gex_profile = calculate_gex_profile(chain, spot)
    except Exception:
        pass

    return MarketContext(
        spot=spot, underlying=underlying.upper(),
        funding_8h_pct=funding_8h,
        cb_size_mult=cb_mult,
        win_rate=win_rate, avg_R=avg_r,
        portfolio_value=portfolio_value,
        gex_profile=gex_profile,
    )


async def _option_chain_or_none(*, underlying: str, app, spot: float):
    adapter = _adm.get_adapter() or getattr(app.state, "adapter", None)
    inst = registry.get_instrument(underlying.upper()) or \
        registry.get_instrument(underlying.upper().replace("USD", ""))   # "BTCUSD" → "BTC"
    if adapter is None or inst is None or not getattr(inst, "has_options", False):
        return None
    try:
        chain = await adapter.get_option_chain(inst)
        log.info(f"Chain for {underlying}: {'None' if chain is None else len(chain)} items")
        return enrich_chain(chain, spot=spot)
    except Exception as e:
        log.error(f"Failed to fetch option chain for {underlying}: {e}")
        return None


# ─── /candidates ───────────────────────────────────────────────────────


class _CandidateRow(BaseModel):
    signal_id: str
    source: str = "engine"          # "engine" (scalping/triple-ST) | "edge" (validated feed)
    strategy: str
    underlying: str
    direction: str
    instrument_type: str
    option_symbol: Optional[str] = None
    strike: Optional[float] = None
    dte: Optional[int] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    premium: Optional[float] = None
    contracts: float
    leverage: float
    notional_usd: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    expected_r: float
    funding_cost_usd: float = 0.0
    theta_burn_usd: float = 0.0
    liquidity_score: Optional[float] = None
    freeze_token: str
    freeze_token_ttl_ms: int
    status: str
    reason: str
    warnings: list[str] = []
    chain_age_ms: Optional[int] = None
    structure_summary: Optional[str] = None
    structure_max_loss_usd: Optional[float] = None
    structure_max_profit_usd: Optional[float] = None


class _CandidatesResponse(BaseModel):
    candidates: list[_CandidateRow]
    timestamp_ms: int


def _signal_source(strategy: str) -> str:
    """Which feed a signal came from — drives the FE source badge."""
    return "edge" if strategy.startswith("edge/") else "engine"


def _row_from_decision(*, signal_id: str, signal: SignalContext,
                       decision: DerivativesDecision) -> _CandidateRow:
    c = decision.chosen
    struct = getattr(c, "structure", None) if c else None
    return _CandidateRow(
        signal_id=signal_id,
        source=_signal_source(signal.strategy),
        strategy=signal.strategy,
        underlying=signal.underlying,
        direction=signal.direction,
        instrument_type=c.instrument_type if c else "",
        option_symbol=getattr(c, "option_symbol", None) if c else None,
        strike=getattr(c, "strike", None) if c else None,
        dte=getattr(c, "dte", None) if c else None,
        delta=getattr(c, "delta", None) if c else None,
        gamma=getattr(c, "gamma", None) if c else None,
        theta=getattr(c, "theta", None) if c else None,
        vega=getattr(c, "vega", None) if c else None,
        premium=getattr(c, "premium_usd", None) if c else None,
        contracts=c.contracts if c else 0.0,
        leverage=c.leverage if c else 1.0,
        notional_usd=c.notional_usd if c else 0.0,
        stop_loss=c.stop_loss if c else None,
        take_profit=c.take_profit if c else None,
        expected_r=c.expected_r if c else 0.0,
        funding_cost_usd=c.projected_funding_cost_usd if c else 0.0,
        theta_burn_usd=c.projected_theta_burn_usd if c else 0.0,
        liquidity_score=(c.liquidity.composite if (c and c.liquidity) else None),
        freeze_token=decision.freeze_token or "",
        freeze_token_ttl_ms=decision.freeze_token_ttl_ms,
        status=decision.status.value,
        reason=decision.reason,
        warnings=decision.warnings,
        structure_summary=(struct.summary() if struct else None),
        structure_max_loss_usd=(struct.max_loss_usd if struct else None),
        structure_max_profit_usd=(struct.max_profit_usd if struct else None),
    )


def _cached_rows(
    app, leg: str, *, strategy: Optional[str], underlying: Optional[str],
) -> tuple[list[_CandidateRow], int]:
    """Read rows for one leg ("futures"|"options") from the background
    scanner's cached snapshot, filtered by strategy/underlying.

    The scanner is the SOLE producer (it runs the heavy selector pipeline
    off-thread once per tick). Read endpoints never recompute — that is what
    keeps the event loop free and the server responsive under FE polling.
    """
    cache = getattr(getattr(app, "state", None), "derivatives_scan_cache", None) or {}
    ts = int(cache.get("last_scan_ms", 0))
    out: list[_CandidateRow] = []
    for d in cache.get(leg, []) or []:
        row = d if isinstance(d, _CandidateRow) else _CandidateRow(**d)
        # Edge is a cross-strategy validated feed — its rows show on every tab
        # regardless of the per-strategy filter, so a proven signal is never
        # hidden. Engine rows still respect the strategy filter.
        if strategy and row.strategy != strategy and row.source != "edge":
            continue
        if underlying and row.underlying.upper() != underlying.upper():
            continue
        out.append(row)
    return out, ts


@router.get("/candidates", response_model=_CandidatesResponse)
async def candidates(
    request: Request,
    strategy: Optional[str] = Query(default=None),
    underlying: Optional[str] = Query(default=None),
):
    """Combined candidate rows (futures + options) from the scanner cache.

    Filter by strategy (e.g. 'scalping/price_action') or underlying. The
    split `/candidates/futures` and `/candidates/options` endpoints below
    feed the parallel FE tables; this combined view is kept for back-compat.
    """
    fut, ts = _cached_rows(request.app, "futures", strategy=strategy, underlying=underlying)
    opt, _ = _cached_rows(request.app, "options", strategy=strategy, underlying=underlying)
    return _CandidatesResponse(candidates=fut + opt, timestamp_ms=ts)


# ─── /candidates/futures + /candidates/options ────────────────────────


async def _both_rows(
    request: Request,
    *,
    strategy_filter: Optional[str],
    underlying_filter: Optional[str],
) -> tuple[list[_CandidateRow], list[_CandidateRow], int]:
    """Returns (futures_rows, options_rows, timestamp_ms).

    One pass through armed signals → one `decide_both()` per signal →
    two row lists. Profile-disabled strategies are skipped here so
    every row the FE sees is actionable.
    """
    futures_rows: list[_CandidateRow] = []
    options_rows: list[_CandidateRow] = []
    now_ms = int(time.time() * 1000)
    overrides = _profile_overrides(request.app)
    engine_cfg = get_engine_config(request.app)

    # The collection is synchronous and heavy (~4.6s scalping scan) — run it
    # OFF the event loop so the scanner tick never freezes the server.
    signals = await asyncio.to_thread(
        _collect_armed_signals, request,
        strategy_filter=strategy_filter, underlying_filter=underlying_filter,
    )
    log.info("DERIV _both_rows: collected %d armed signals", len(signals))
    market_cache: dict[str, MarketContext] = {}
    chain_cache: dict[str, Any] = {}

    for signal_id, sig in signals:
        prof = overrides.get(sig.strategy) or get_profile(sig.strategy)
        if not prof.enabled:
            log.debug("DERIV _both_rows: skip %s (profile disabled)", sig.strategy)
            continue
        ul = sig.underlying.upper()
        if ul not in market_cache:
            try:
                market_cache[ul] = await _market_context(
                    underlying=ul, app=request.app,
                    signal_score=sig.signal_score,
                )
            except HTTPException as he:
                log.warning("DERIV _both_rows: market_context failed for %s: %s", ul, he.detail)
                continue
        if ul not in chain_cache:
            chain_cache[ul] = await _option_chain_or_none(
                underlying=ul, app=request.app, spot=market_cache[ul].spot,
            )
        try:
            if engine_cfg.engine_mode == EngineMode.NATIVE:
                dual = _native_engine.decide_both(
                    signal=sig, market=market_cache[ul], chain=chain_cache[ul],
                    profile_overrides=overrides, config=engine_cfg,
                )
            else:
                dual = _decide_both(
                    signal=sig, market=market_cache[ul], chain=chain_cache[ul],
                    profile_overrides=overrides,
                )
        except Exception as dec_exc:
            import traceback
            log.warning("DERIV _both_rows: decide_both crashed for %s/%s: %s\n%s",
                        sig.strategy, ul, dec_exc, traceback.format_exc())
            continue

        fut_status = dual.futures.status if dual.futures else None
        opt_status = dual.options.status if dual.options else None
        log.info("DERIV _both_rows: %s/%s → futures=%s options=%s",
                 sig.strategy, ul, fut_status, opt_status)

        # Audit each leg so the operator's 7-day observation feed sees
        # both arms even before either is enabled for auto-exec.
        try:
            for leg in (dual.futures, dual.options):
                if leg is not None:
                    derivatives_audit.record(decision=leg, signal=sig, market=market_cache[ul])
        except Exception:
            pass

        if dual.futures and dual.futures.status == DecisionStatus.OK and dual.futures.chosen:
            futures_rows.append(
                _row_from_decision(signal_id=signal_id, signal=sig, decision=dual.futures)
            )
        if dual.options and dual.options.status == DecisionStatus.OK and dual.options.chosen:
            options_rows.append(
                _row_from_decision(signal_id=signal_id, signal=sig, decision=dual.options)
            )
    log.info("DERIV _both_rows: produced %d futures + %d options rows", len(futures_rows), len(options_rows))
    return futures_rows, options_rows, now_ms


@router.get("/candidates/futures", response_model=_CandidatesResponse)
async def candidates_futures(
    request: Request,
    strategy: Optional[str] = Query(default=None),
    underlying: Optional[str] = Query(default=None),
):
    """Futures-only candidate rows from the scanner cache. Each row carries
    its OWN freeze_token — independent of any options row for the same
    signal. Served from cache (no live scan) so the FE can poll freely."""
    fut, ts = _cached_rows(request.app, "futures", strategy=strategy, underlying=underlying)
    return _CandidatesResponse(candidates=fut, timestamp_ms=ts)


@router.get("/candidates/options", response_model=_CandidatesResponse)
async def candidates_options(
    request: Request,
    strategy: Optional[str] = Query(default=None),
    underlying: Optional[str] = Query(default=None),
):
    """Options-only candidate rows from the scanner cache. Each row carries
    its OWN freeze_token. Served from cache (no live scan)."""
    opt, ts = _cached_rows(request.app, "options", strategy=strategy, underlying=underlying)
    return _CandidatesResponse(candidates=opt, timestamp_ms=ts)


# ─── /scan — cached background snapshot ───────────────────────────────


class _ScanResponse(BaseModel):
    futures: list[_CandidateRow]
    options: list[_CandidateRow]
    algo_mode: bool
    last_scan_ms: int
    next_scan_ms: int
    auto_exec_attempts: int = 0
    auto_exec_accepted: int = 0


@router.get("/scan")
async def scan(request: Request) -> _ScanResponse:
    """Read the cached scanner snapshot maintained by the background
    derivatives scanner. Fast — no live work. The FE polls this every
    30s instead of triggering a fresh selector pipeline on every refresh.

    The scanner writes its output to `app.state.derivatives_scan_cache`
    on each tick; this endpoint just returns the cached snapshot.
    """
    cache = getattr(request.app.state, "derivatives_scan_cache", None)
    algo_on = bool(getattr(request.app.state, "algo_mode", False))
    if cache is None:
        return _ScanResponse(
            futures=[], options=[], algo_mode=algo_on,
            last_scan_ms=0, next_scan_ms=0,
        )
    return _ScanResponse(
        futures=cache.get("futures", []),
        options=cache.get("options", []),
        algo_mode=algo_on,
        last_scan_ms=cache.get("last_scan_ms", 0),
        next_scan_ms=cache.get("next_scan_ms", 0),
        auto_exec_attempts=cache.get("auto_exec_attempts", 0),
        auto_exec_accepted=cache.get("auto_exec_accepted", 0),
    )


# ─── /preview ──────────────────────────────────────────────────────────


@router.get("/preview")
async def preview(
    request: Request,
    strategy: str = Query(...),
    underlying: str = Query(...),
    direction: str = Query(default="long"),
    entry: float = Query(...),
    stop_loss: float = Query(...),
    take_profit: Optional[float] = Query(default=None),
    atr: float = Query(default=0.0),
    signal_score: float = Query(default=0.0),
    expected_hold_minutes: Optional[int] = Query(default=None),
):
    """Run the selector against an ad-hoc signal. Used by the FE detail
    drawer (clicking a row → preview the alternative candidates) and by
    the per-strategy execute path before submission."""
    sig = SignalContext(
        strategy=strategy, underlying=underlying.upper(), direction=direction,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit,
        atr=atr, signal_score=signal_score,
        expected_hold_minutes=expected_hold_minutes,
    )
    overrides = _profile_overrides(request.app)
    market = await _market_context(
        underlying=underlying, app=request.app, signal_score=signal_score,
    )
    chain = await _option_chain_or_none(
        underlying=underlying, app=request.app, spot=market.spot,
    )
    decision = preview_one(
        signal=sig, market=market, chain=chain, profile_overrides=overrides,
    )
    try:
        derivatives_audit.record(decision=decision, signal=sig, market=market)
    except Exception:
        pass
    return decision


# ─── /execute ──────────────────────────────────────────────────────────


class _ExecuteRequest(BaseModel):
    freeze_token: str
    candidate_idx: int = 0          # 0 = chosen; 1-3 = alternatives
    # Originating strategy slug ("scalping/price_action", "directional", …).
    # Stamped into the position notes so the FE can attribute the executed
    # position back to its engine (matches the auto-exec note format), keeping
    # the Grok and Sterling candidate tables strictly engine-specific.
    strategy: Optional[str] = None


class _ExecuteResponse(BaseModel):
    accepted: bool
    mode: str
    underlying: str
    instrument_type: str
    direction: str
    size: float
    leverage: float
    order_id: Optional[str] = None
    paper_position_id: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str
    code: str = ""
    reason: str = ""
    timestamp_ms: int


@router.post("/execute")
async def execute(body: _ExecuteRequest, request: Request) -> _ExecuteResponse:
    """Execute the frozen decision. The freeze_token MUST match a still-
    valid entry in the store, or we reject with `code=stale_candidate`."""
    now_ms = int(time.time() * 1000)
    store = get_freeze_store()
    decision = store.consume(body.freeze_token)
    if decision is None:
        raise HTTPException(
            status_code=409, detail={
                "code": "stale_candidate",
                "reason": "freeze_token expired or already consumed — re-fetch /derivatives/candidates",
            },
        )

    # Choose chosen vs. alternative
    if body.candidate_idx == 0:
        candidate = decision.chosen
    elif 1 <= body.candidate_idx <= len(decision.alternatives):
        candidate = decision.alternatives[body.candidate_idx - 1]
    else:
        raise HTTPException(status_code=400, detail="candidate_idx out of range")

    if candidate is None:
        raise HTTPException(status_code=400, detail="decision had no chosen candidate")

    # Multi-leg structures (defined-risk spreads/condors) → submit each leg
    # individually, track them as a group. Single-leg candidates route through
    # the existing single-order path unchanged.
    # Engine-attribution tag — mirrors the auto-exec note format
    # ("… {strategy} freeze=…") so the FE can scope positions per engine.
    strat_tag = f"{body.strategy} " if body.strategy else ""

    if candidate.structure and len(candidate.structure.legs) > 1:
        from app.api.v1.endpoints.trading import LiveOrderRequest, place_live_order

        leg_results: list[dict] = []
        for leg in candidate.structure.legs:
            leg_symbol = leg.option_symbol
            if not leg_symbol:
                leg_results.append({"error": "missing option_symbol on leg", "strike": leg.strike})
                continue
            leg_order = LiveOrderRequest(
                underlying=candidate.underlying,
                direction=leg.side if leg.side == "buy" else "short",
                instrument_type="options",
                size=float(candidate.contracts * leg.ratio),
                leverage=1.0,
                order_type="market",
                stop_loss=None,
                take_profit=None,
                option_symbol=leg_symbol,
                notes=f"[DERIV-{candidate.structure.structure_type}] {strat_tag}freeze={body.freeze_token[:8]} leg={leg.option_type}@{leg.strike}",
            )
            try:
                leg_resp = await place_live_order(leg_order, request)
                leg_results.append({
                    "accepted": leg_resp.status not in ("rejected", "error"),
                    "order_id": leg_resp.order_id,
                    "paper_position_id": leg_resp.paper_position_id,
                    "option_symbol": leg_symbol,
                    "mode": leg_resp.mode,
                })
            except Exception as exc:
                leg_results.append({"error": str(exc), "strike": leg.strike})

        all_ok = all(r.get("accepted", False) for r in leg_results)
        n_ok = sum(1 for r in leg_results if r.get("accepted"))
        n_total = len(leg_results)
        reason_msg = f"{candidate.structure.structure_type}: {n_total} legs {'all OK' if all_ok else f'{n_ok}/{n_total} accepted'}"
        return _ExecuteResponse(
            accepted=all_ok,
            mode=leg_results[0].get("mode", "paper") if leg_results else "paper",
            underlying=candidate.underlying,
            instrument_type="options",
            direction=candidate.direction,
            size=float(candidate.contracts),
            leverage=1.0,
            order_id=",".join(r.get("order_id", "") or "" for r in leg_results) or None,
            paper_position_id=",".join(r.get("paper_position_id", "") or "" for r in leg_results) or None,
            entry_price=candidate.entry_price,
            stop_loss=None,
            take_profit=None,
            status="filled" if all_ok else "partial",
            code="multi_leg" if all_ok else "multi_leg_partial",
            reason=reason_msg,
        )

    # ── Single-leg path (futures or single options) ─────────────────────
    from app.api.v1.endpoints.trading import LiveOrderRequest, place_live_order
    order = LiveOrderRequest(
        underlying=candidate.underlying,
        direction=candidate.direction,
        instrument_type=candidate.instrument_type,
        size=float(candidate.contracts),
        leverage=float(candidate.leverage),
        order_type="market",
        stop_loss=candidate.stop_loss,
        take_profit=candidate.take_profit,
        option_symbol=candidate.option_symbol,
        delta=candidate.delta,
        gamma=candidate.gamma,
        theta=candidate.theta,
        vega=candidate.vega,
        projected_theta_burn_usd=candidate.projected_theta_burn_usd,
        liquidity=candidate.liquidity,
        expected_r=candidate.expected_r,
        dte=candidate.dte,
        notes=f"[DERIV-{candidate.instrument_type.upper()}] {strat_tag}freeze={body.freeze_token[:8]} R={candidate.expected_r:.2f}",
    )
    try:
        resp = await place_live_order(order, request)
    except Exception as e:
        store.restore(body.freeze_token, decision)
        raise

    return _ExecuteResponse(
        accepted=resp.status not in ("rejected", "error"),
        mode=resp.mode,
        underlying=candidate.underlying,
        instrument_type=candidate.instrument_type,
        direction=candidate.direction,
        size=float(candidate.contracts),
        leverage=float(candidate.leverage),
        order_id=resp.order_id,
        paper_position_id=resp.paper_position_id,
        entry_price=resp.entry_price,
        stop_loss=candidate.stop_loss,
        take_profit=candidate.take_profit,
        status=resp.status,
        reason=resp.message,
        timestamp_ms=resp.timestamp_ms or now_ms,
    )


# ─── /config ───────────────────────────────────────────────────────────


class _ConfigResponse(BaseModel):
    profiles: dict[str, StrategyDerivativesProfile]
    defaults: dict[str, StrategyDerivativesProfile]


class _ConfigPatchRequest(BaseModel):
    profile: StrategyDerivativesProfile


class _ConfigPatchGlobalRequest(BaseModel):
    enabled: Optional[bool] = None
    auto_execute_futures: Optional[bool] = None
    auto_execute_options: Optional[bool] = None


@router.get("/config")
async def get_config(request: Request) -> _ConfigResponse:
    from app.engines.derivatives.profiles import DEFAULT_PROFILES
    return _ConfigResponse(profiles=_profile_overrides(request.app), defaults=DEFAULT_PROFILES)


@router.post("/config")
async def patch_config(body: _ConfigPatchRequest, request: Request) -> _ConfigResponse:
    from app.services.db import set_config
    import json

    overrides = _profile_overrides(request.app)
    overrides[body.profile.strategy] = body.profile

    # Persist to DB (StrategyDerivativesProfile is a pydantic model — model_dump,
    # not dataclasses.asdict).
    try:
        dict_overrides = {k: v.model_dump() for k, v in overrides.items()}
        set_config("derivatives_profiles", json.dumps(dict_overrides))
    except Exception as e:
        log.warning(f"Failed to persist derivatives_profiles: {e}")
        
    from app.engines.derivatives.profiles import DEFAULT_PROFILES
    return _ConfigResponse(profiles=overrides, defaults=DEFAULT_PROFILES)


@router.delete("/config")
async def reset_all_config(request: Request) -> _ConfigResponse:
    from app.services.db import set_config
    import json
    try:
        set_config("derivatives_profiles", json.dumps({}))
        if hasattr(request.app.state, "derivatives_profiles"):
            request.app.state.derivatives_profiles = {}
    except Exception as e:
        log.warning(f"Failed to reset derivatives_profiles: {e}")
        
    from app.engines.derivatives.profiles import DEFAULT_PROFILES
    return _ConfigResponse(profiles={}, defaults=DEFAULT_PROFILES)


@router.post("/config/global")
async def patch_config_global(body: _ConfigPatchGlobalRequest, request: Request) -> _ConfigResponse:
    from app.services.db import set_config
    import json

    overrides = _profile_overrides(request.app)
    for p in overrides.values():
        if body.enabled is not None:
            p.enabled = body.enabled
        if body.auto_execute_futures is not None:
            p.auto_execute_futures = body.auto_execute_futures
        if body.auto_execute_options is not None:
            p.auto_execute_options = body.auto_execute_options

    try:
        dict_overrides = {k: v.model_dump() for k, v in overrides.items()}
        set_config("derivatives_profiles", json.dumps(dict_overrides))
    except Exception as e:
        log.warning(f"Failed to persist derivatives_profiles: {e}")
        
    from app.engines.derivatives.profiles import DEFAULT_PROFILES
    return _ConfigResponse(profiles=overrides, defaults=DEFAULT_PROFILES)


@router.get("/config/engine")
async def get_engine_config_ep(request: Request) -> DerivativesEngineConfig:
    return get_engine_config(request.app)


@router.post("/config/engine")
async def set_engine_config_ep(
    body: DerivativesEngineConfig, request: Request
) -> DerivativesEngineConfig:
    return set_engine_config(request.app, body)


# ─── /study/run, /study/status, /study/report ──────────────────────────


@router.post("/study/run")
async def study_run(body: dict, request: Request) -> dict:
    """Trigger a derivatives edge study run.

    Only one study runs at a time. Returns 409 if a study is already
    running. The study runs in the background; poll GET /study/status
    for progress.
    """
    import asyncio
    from study.run import StudyRunner, StudyRunRequest

    runs = getattr(request.app.state, "study_runs", {})
    for rid, state in runs.items():
        if state.status in ("starting", "running"):
            raise HTTPException(
                status_code=409,
                detail=f"Study already running: {rid}",
            )

    req = StudyRunRequest(
        symbols=body.get("symbols", ["BTCUSD", "ETHUSD", "SOLUSD"]),
        timeframes=body.get("timeframes", ["15m", "30m", "1h", "2h", "4h"]),
        validation_method=body.get("validation_method", 1),
    )

    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", "..", "..", ".."))

    runner = StudyRunner(app=request.app, data_dir=root, output_dir=root)
    state = runner.init_run(req)
    spawn_background(runner.run(req), name=f"study-run-{state.run_id}")

    return {"run_id": state.run_id, "status": state.status, "n_configs": 0}


@router.get("/study/status/{run_id}")
async def study_status(run_id: str, request: Request) -> dict:
    """Poll the status of a running/completed study."""
    runs = getattr(request.app.state, "study_runs", {})
    state = runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"no study run with id {run_id}")
    return {
        "run_id": state.run_id,
        "status": state.status,
        "progress_pct": state.progress_pct,
        "current_stage": state.current_stage,
        "elapsed_seconds": state.elapsed_seconds,
        "error": state.error,
        "n_configs": state.n_configs,
        "n_survivors": state.n_survivors,
    }


@router.get("/study/report")
async def study_report(request: Request) -> dict:
    """Return the stored Phase-1 study artifacts.

    Reads generated files first (from last study run). Falls back to
    static artifacts if no generated files exist. The FE selector can
    display whichever is available."""
    import os
    cfg = get_engine_config(request.app)
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", "..", "..", ".."))

    def _read(name: str):
        for d in (root, os.path.join(root, "backend")):
            p = os.path.join(d, name)
            if os.path.exists(p):
                try:
                    with open(p) as fh:
                        return {"text": fh.read(), "generated_at": int(os.path.getmtime(p))}
                except Exception:
                    pass
        return None

    study = _read("DERIVATIVES_EDGE_STUDY.md")
    gate = _read("GATE_OVERFILTER.md")

    # Also try the gate overfilter CSV
    gate_csv = _read("derivatives_gate_overfilter.csv")

    return {
        "validation_method": cfg.validation_method,
        "study": study["text"] if study else None,
        "study_generated_at": study["generated_at"] if study else None,
        "gate_overfilter": gate["text"] if gate else None,
        "has_csv": gate_csv is not None,
    }


# ─── /greeks-budget ────────────────────────────────────────────────────


@router.get("/greeks-budget")
async def greeks_budget_state(request: Request) -> dict:
    """Current portfolio Greeks vs budget caps, with per-position breakdown.

    Reads `app.state.greeks_budget_checker` (the live aggregator) and
    refreshes each open option position via the Phase 1 aggregator
    helpers so the response reflects current spot/IV/T — not stale
    entry-time snapshots.
    """
    from app.engines.risk.greeks_budget import GreeksBudget
    from app.engines.risk import portfolio_greeks_aggregator as _agg
    from app.services import paper_store as _ps
    from app.services import adapter_manager as _adm

    checker = getattr(request.app.state, "greeks_budget_checker", None)
    budget = (checker.budget if checker else GreeksBudget())
    adapter = _adm.get_adapter() or getattr(request.app.state, "adapter", None)

    open_positions = [
        p for p in _ps.list_positions()
        if p.status.value in ("open", "partially_closed")
    ]

    if adapter is None:
        return {
            "budget": budget.__dict__,
            "portfolio_value": (checker.pv if checker else 0.0),
            "net_greeks": {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0},
            "positions": [],
        }

    # Per-position refresh
    per_position = []
    net = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
    for pos in open_positions:
        ul = pos.underlying.upper()
        try:
            inst = registry.get_instrument(ul)
            spot = float(await adapter.get_index_price(inst)) if inst else 0.0
        except Exception:
            spot = float(pos.entry_spot_price or 0.0)
        g = _agg.refresh_position_greeks(pos, current_spot=spot)
        notional = spot * float(pos.sized_trade.qty or 0)   # qty = lots × lot size (cv)
        per_position.append({
            "id": pos.id, "underlying": ul,
            "instrument_type": pos.sized_trade.structure.structure_type,
            "contracts": pos.sized_trade.contracts,
            "notional_usd": notional,
            "delta": g.delta, "gamma": g.gamma, "vega": g.vega,
            "theta": g.theta, "rho": g.rho,
        })
        net["delta"] += g.delta * notional
        net["gamma"] += g.gamma * notional
        net["vega"]  += g.vega  * notional
        net["theta"] += g.theta * notional
        net["rho"]   += g.rho   * notional

    pv = float(checker.pv) if checker else 100_000.0
    usage = {k: (v / pv if pv > 0 else 0.0) for k, v in net.items()}
    return {
        "budget": budget.__dict__,
        "portfolio_value": pv,
        "net_greeks": net,
        "usage_pct_of_nav": usage,
        "positions": per_position,
        "timestamp_ms": int(time.time() * 1000),
    }


# ─── /funding & /book ──────────────────────────────────────────────────


@router.get("/funding/{underlying}")
async def funding(underlying: str, request: Request) -> dict:
    from app.services import adapter_manager as _adm
    adapter = _adm.get_adapter() or getattr(request.app.state, "adapter", None)
    inst = registry.get_instrument(underlying.upper())
    if adapter is None or inst is None:
        raise HTTPException(status_code=503, detail="adapter or instrument unavailable")
    try:
        pid = await adapter.get_product_id(inst.delta_perp_symbol or f"{underlying.upper()}USD")
        return await adapter.get_funding_rate(pid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"funding fetch failed: {exc}") from exc


@router.get("/book/{symbol}")
async def book(symbol: str, request: Request, depth: int = Query(default=10, ge=1, le=50)) -> dict:
    adapter = getattr(request.app.state, "adapter", None)
    if adapter is None:
        raise HTTPException(status_code=503, detail="adapter unavailable")
    try:
        pid = await adapter.get_product_id(symbol)
        return await adapter.get_l2_book(pid, depth=depth)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"book fetch failed: {exc}") from exc


# ─── edge feed (validated 4h winners) ─────────────────────────────────


def _edge_csv_path() -> str:
    """Locate the edge results CSV. Prefers `robustness_scan_results.csv`
    (the CPCV+Monte-Carlo enriched matrix from `robustness_scan.py`) so the
    live feed gates on out-of-sample Sharpe + P(loss), and falls back to the
    raw `backtest_edge_results.csv` if only that exists."""
    override = os.environ.get("STERLING_EDGE_CSV")
    if override:
        return override
    here = Path(__file__).resolve()
    # parents[4] = backend/ (where robustness_scan.py writes), parents[5] = repo root.
    roots = [here.parents[4], here.parents[5], Path.cwd(), Path.cwd().parent]
    for name in ("robustness_scan_results.csv", "backtest_edge_results.csv"):
        for root in roots:
            c = root / name
            if c.exists():
                return str(c)
    return str(here.parents[5] / "backtest_edge_results.csv")


def _edge_gate(app):
    """The operator-tunable EdgeGate, seeded with defaults on first access.
    Adjusted via POST /derivatives/edge-gate; in-memory like the profiles."""
    from app.engines.edge.registry import EdgeGate
    gate = getattr(getattr(app, "state", None), "edge_gate", None)
    if gate is None:
        # Deflation-first default: admit only combos that (a) survive CPCV
        # (OOS Sharpe > 0), (b) have Monte-Carlo P(loss) ≤ 35%, (c) clear the
        # deflated Sharpe at ≥ 0.5 (more-likely-than-not a real edge AFTER
        # correcting for the full search grid), and (d) actually beat
        # buy-and-hold on return AND drawdown. Raw in-sample Sharpe is relaxed
        # (min_sharpe=0) because deflation/OOS are the real filters.
        # NOTE: with the current strategy zoo this admits ZERO combos — nothing
        # survives honest deflation (best DSR ≈ 0.09 at full-grid trials). That
        # is the correct, disciplined outcome; relax min_dsr/require_beats_hold
        # via POST /derivatives/edge-gate for research/exploration.
        gate = EdgeGate(min_sharpe=0.0, min_trades=20,
                        min_oos_sharpe=0.0, max_p_loss=0.35,
                        min_dsr=0.5, require_beats_hold=True)
        if hasattr(app, "state"):
            app.state.edge_gate = gate
    return gate


def _edge_registry(app):
    """Load + cache the edge registry on app.state, gated by `_edge_gate(app)`.
    Re-run the backtest and restart (or clear app.state.edge_registry) to
    refresh the allow-list. Changing the gate clears the cache so the next
    access rebuilds with the new thresholds."""
    from app.engines.edge.registry import EdgeRegistry, load_edge_registry
    reg = getattr(getattr(app, "state", None), "edge_registry", None)
    if reg is None:
        try:
            reg = load_edge_registry(_edge_csv_path(), gate=_edge_gate(app))
        except Exception:
            reg = EdgeRegistry()
        if hasattr(app, "state"):
            app.state.edge_registry = reg
    return reg


def _edge_candle_fetcher(symbol: str, tf: str, lookback_bars: int):
    """Pull recent bars at `tf` from the OHLCV store as Candle objects."""
    from app.schemas.market import Candle
    from app.services import ohlcv_store
    rows = ohlcv_store.get_candles(symbol.upper(), tf, limit=lookback_bars)
    return [
        Candle(timestamp_ms=int(r["time"]) * 1000, open=r["open"], high=r["high"],
               low=r["low"], close=r["close"], volume=r.get("volume", 0.0))
        for r in rows
    ]


def _collect_edge_signals(
    *, strategy_filter: Optional[str], underlying_filter: Optional[str], app,
) -> list[tuple[str, SignalContext]]:
    """Generate edge-feed signals from registry-admitted combos, honouring the
    same strategy/underlying filters the candidate endpoints use."""
    from app.engines.edge.signals import generate_edge_signals

    # An explicit non-edge strategy filter means the caller wants the other feed.
    if strategy_filter is not None and not strategy_filter.startswith("edge"):
        return []

    reg = _edge_registry(app)
    if not reg.all():
        return []

    out: list[tuple[str, SignalContext]] = []
    for sid, sig in generate_edge_signals(reg, fetch_candles=_edge_candle_fetcher):
        if strategy_filter and sig.strategy != strategy_filter:
            continue
        if underlying_filter and sig.underlying.upper() != underlying_filter.upper():
            continue
        out.append((sid, sig))
    return out


# ─── /edge-gate — operator-tunable edge admission thresholds ───────────


class _EdgeGateModel(BaseModel):
    min_net_return: float = Field(0.0, ge=-1.0, le=100.0)
    min_sharpe: float = Field(0.0, ge=-100.0, le=100.0)
    min_trades: int = Field(20, ge=0)
    # Robustness gate (reads robustness columns). Defaults match the live
    # survivor gate: OOS Sharpe > 0, Monte-Carlo P(loss) ≤ 35%, deflated Sharpe
    # ≥ 0.5, and must beat buy-and-hold.
    min_oos_sharpe: float = Field(0.0, ge=-100.0, le=100.0)
    max_p_loss: float = Field(0.35, ge=0.0, le=1.0)
    min_dsr: float = Field(0.5, ge=0.0, le=1.0)
    require_beats_hold: bool = Field(True)


class _EdgeComboSummary(BaseModel):
    symbol: str
    tf: str
    strategy: str
    profile: str
    trades: int
    sharpe: float
    pf: float
    net_return: float
    signal_score: float
    dsr: float = 1.0
    beats_hold: bool = True


class _EdgeGateResponse(BaseModel):
    gate: _EdgeGateModel
    admitted_count: int
    admitted: list[_EdgeComboSummary]


def _edge_gate_response(app) -> _EdgeGateResponse:
    gate = _edge_gate(app)
    reg = _edge_registry(app)
    admitted = sorted(reg.all(), key=lambda c: -c.signal_score)
    return _EdgeGateResponse(
        gate=_EdgeGateModel(min_net_return=gate.min_net_return,
                            min_sharpe=gate.min_sharpe, min_trades=gate.min_trades,
                            min_oos_sharpe=gate.min_oos_sharpe, max_p_loss=gate.max_p_loss,
                            min_dsr=gate.min_dsr,
                            require_beats_hold=gate.require_beats_hold),
        admitted_count=len(admitted),
        admitted=[_EdgeComboSummary(
            symbol=c.symbol, tf=c.tf, strategy=c.strategy, profile=c.profile,
            trades=c.trades, sharpe=c.sharpe, pf=c.pf,
            net_return=c.net_return, signal_score=c.signal_score,
            dsr=c.dsr, beats_hold=c.beats_hold,
        ) for c in admitted],
    )


@router.get("/edge-gate")
async def get_edge_gate(request: Request) -> _EdgeGateResponse:
    return _edge_gate_response(request.app)


@router.post("/edge-gate")
async def set_edge_gate(body: _EdgeGateModel, request: Request) -> _EdgeGateResponse:
    """Update the edge admission thresholds and rebuild the allow-list. Changes
    are in-memory (lost on restart), matching the per-strategy profile pattern."""
    from app.engines.edge.registry import EdgeGate
    request.app.state.edge_gate = EdgeGate(
        min_net_return=body.min_net_return,
        min_sharpe=body.min_sharpe,
        min_trades=body.min_trades,
        min_oos_sharpe=body.min_oos_sharpe,
        max_p_loss=body.max_p_loss,
        min_dsr=body.min_dsr,
        require_beats_hold=body.require_beats_hold,
    )
    request.app.state.edge_registry = None       # force rebuild with new gate
    return _edge_gate_response(request.app)


@router.get("/strategy-catalog")
async def strategy_catalog(request: Request) -> dict:
    """Plain-English catalog of every strategy + the live, validated combos it is
    running. Powers the strategy info panel so a user can see what each cryptic id
    ('ma_crossover', 'smc', …) actually does, on what timeframe, long/short, which
    engine, how it routes to futures/options, and how each live config performs."""
    from app.engines.edge.catalog import build_catalog
    reg = _edge_registry(request.app)
    return {
        "strategies": build_catalog(reg),
        "engines": {
            "edge_feed": ("Backtest-validated, long-only signals (the functions in "
                          "edge/strategies.py). Only combos that survive the full gate — "
                          "out-of-sample Sharpe > 0, Monte-Carlo P(loss) ≤ 35%, deflated "
                          "Sharpe ≥ 0.5 (multiple-testing corrected over the whole search "
                          "grid), and beating buy-and-hold on return AND drawdown — are "
                          "admitted. With the current strategy set that is ZERO combos: "
                          "nothing survives honest deflation. These feed both candidate "
                          "tables."),
            "scalping_scanner": ("Intraday near-4H-level setups (some bidirectional). "
                                 "Same strategy NAMES but different logic from the edge "
                                 "feed — always check the engine label."),
        },
        "routing": ("A strategy only produces a directional SIGNAL. The derivatives "
                    "selector then decides whether to express it as a FUTURE or an "
                    "OPTION based on liquidity and the Greeks budget — which is why the "
                    "same signal can surface in either table."),
        "gate": _edge_gate_response(request.app).gate.model_dump(),
    }


# ─── armed-signal collection (per-strategy adapters) ──────────────────


def _collect_armed_signals(
    request: Request, *, strategy_filter: Optional[str], underlying_filter: Optional[str],
) -> list[tuple[str, SignalContext]]:
    """Pull armed signals from every strategy module that the selector
    can drive. Returns `[(signal_id, SignalContext)]`.

    Synchronous and CPU/IO-heavy (the scalping scan alone is ~4.6s). It has
    NO awaits, so callers MUST run it via `asyncio.to_thread` — running it
    directly on the event loop blocks every other request (the cause of the
    wedged-server bug). Only the background scanner calls it now.

    Defensive — a missing scan helper or single-strategy crash doesn't
    break the candidates feed. The FE always falls back to the per-row
    /preview endpoint when this returns empty.
    """
    out: list[tuple[str, SignalContext]] = []

    # Sterling Engine (Conservative/Balanced/Aggressive)
    is_sterling = strategy_filter is None or any(strategy_filter.startswith(p) for p in ["conservative", "balanced", "aggressive", "scalping"])
    if is_sterling:
        try:
            from app.api.v1.endpoints import sterling_engine as _scalp
            from app.services import adapter_manager
            cfg = _scalp._effective_config(request)
            scan = _scalp._scan_all(cfg, adapter_manager.get_data_source())
            for sig in (getattr(scan, "signals", None) or []):
                if not sig.entry_ok:
                    continue
                prof = getattr(sig, "profile", "scalping")
                strat = f"{prof}/{sig.strategy}"
                if strategy_filter and strat != strategy_filter:
                    continue
                if underlying_filter and sig.underlying.upper() != underlying_filter.upper():
                    continue
                signal_id = f"scalp:{sig.underlying}:{strat}:{sig.timestamp_ms}"
                entry = sig.entry or 0.0
                stop = sig.stop_loss or 0.0
                # Real stop distance feeds the SL/TP solver — a 0.0 atr starved
                # the sizing path and is a known cause of empty candidate tables.
                atr = abs(entry - stop) if (entry and stop) else 0.0
                # The scalping engine has no numeric confidence, so tier the score
                # by readiness: an executable signal cleared more gates than an
                # armed-but-not-executable one. Beats a flat placeholder.
                score = 65.0 if sig.executable else 50.0
                out.append((signal_id, SignalContext(
                    strategy=strat, underlying=sig.underlying, direction=sig.direction,
                    entry=entry, stop_loss=stop,
                    take_profit=sig.take_profit, atr=atr,
                    rr_target=2.0, signal_score=score,
                    signal_strength="STRONG" if sig.executable else "SIGNAL",
                    expected_hold_minutes=75, mode_name="scalping",
                    presized=True,
                )))
        except Exception as e:
            import traceback
            log.error(f"Error collecting scalping signals for derivatives: {e}\n{traceback.format_exc()}")

    # Edge-validated feed (4h winners from BACKTEST_EDGE_REPORT)
    try:
        out.extend(_collect_edge_signals(
            strategy_filter=strategy_filter, underlying_filter=underlying_filter,
            app=request.app,
        ))
    except Exception as e:
        import traceback
        log.error(f"Error collecting edge signals for derivatives: {e}\n{traceback.format_exc()}")

    # Directional / Grok feed
    if strategy_filter is None or strategy_filter.startswith("directional"):
        try:
            import time
            from app.services import snapshot_cache
            now_ms = int(time.time() * 1000)
            for sym, snap in list(snapshot_cache._cache.items()):
                if now_ms - snap.computed_at_ms > snapshot_cache._TTL_MS:
                    continue
                if snap.direction in ("long", "short") and snap.current_state in {
                    "ENTRY_ARMED_PULLBACK", "ENTRY_ARMED_CONTINUATION",
                    "CONFIRMED_SETUP_ACTIVE", "EARLY_SETUP_ACTIVE"
                }:
                    # Use the bare `directional` strategy for the profile lookup:
                    # per-track profiles (`directional/swing`, …) default disabled,
                    # which silently dropped every armed directional signal here.
                    strat = "directional"
                    if strategy_filter and strat != strategy_filter:
                        continue
                    if underlying_filter and snap.sym.upper() != underlying_filter.upper():
                        continue
                    
                    signal_id = f"dir:{snap.sym}:{snap.computed_at_ms}"
                    entry = snap.spot_price or 0.0
                    stop = snap.stop_price or entry
                    atr = snap.atr or abs(entry - stop)
                    out.append((signal_id, SignalContext(
                        strategy=strat,
                        underlying=snap.sym,
                        direction=snap.direction,
                        entry=entry,
                        stop_loss=stop,
                        take_profit=snap.target_price,
                        atr=atr,
                        rr_target=2.0,
                        signal_score=snap.signal_score or 50.0,
                        signal_strength=snap.signal_strength or "SIGNAL",
                        expected_hold_minutes=75,
                        mode_name=snap.regime or "swing",
                        presized=False,
                    )))
        except Exception as e:
            import traceback
            log.error(f"Error collecting directional signals for derivatives: {e}\n{traceback.format_exc()}")

    return out
