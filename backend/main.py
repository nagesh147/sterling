import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.services import paper_store
from app.services import exchange_account_store
from app.services import adapter_manager
from app.services import webhook_store as _webhook_store_svc
from app.services import alert_store as _alert_store_bootstrap
from app.services import pnl_history as _pnl_history_svc
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.instruments import router as instruments_router
from app.api.v1.endpoints.directional import router as directional_router
from app.api.v1.endpoints.positions import router as positions_router
from app.api.v1.endpoints.config import router as config_router
from app.api.v1.endpoints.backtest import router as backtest_router
from app.api.v1.endpoints.exchanges import router as exchanges_router
from app.api.v1.endpoints.account import router as account_router
from app.api.v1.endpoints.alerts import router as alerts_router
from app.api.v1.endpoints.webhooks import router as webhooks_router
from app.api.v1.endpoints.options import router as options_router
from app.api.v1.endpoints.stats import router as stats_router
from app.api.v1.endpoints.session import router as session_router
from app.api.v1.endpoints.trading_mode import router as trading_mode_router
from app.api.v1.endpoints.candles import router as candles_router
from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.analytics_baseline import router as analytics_baseline_router
from app.api.v1.endpoints.risk_dashboard import router as risk_dashboard_router
from app.api.v1.endpoints.trading import router as trading_router
from app.api.v1.endpoints.ohlcv import router as ohlcv_router
from app.services import alert_store as _alert_store_svc
from app.services.db_postgres import init_db_schema

log = get_logger(__name__)


async def _background_alert_checker(app: FastAPI, interval: int = 30) -> None:
    """
    Poll instruments with active alerts every `interval` seconds.

    Reuses snapshot_cache entries written by live SSE streams — no duplicate
    exchange calls when the UI is open.  Falls back to a full candle fetch
    only on cache miss (UI closed or stream not running for this instrument).
    """
    import asyncio
    from app.engines.directional.regime_engine import compute_regime
    from app.engines.directional.signal_engine import compute_signal
    from app.engines.directional.setup_engine import evaluate_setup
    from app.engines.directional.orchestrator import compute_ivr
    from app.services.exchanges import instrument_registry as registry
    from app.services import snapshot_cache as _snap_cache
    from app.services import alert_service as _alert_svc

    while True:
        await asyncio.sleep(interval)
        try:
            ad = adapter_manager.get_adapter()
            if not ad:
                continue

            active = [a for a in _alert_store_svc.list_alerts() if a.status.value == "active"]
            if not active:
                continue

            from app.api.v1.endpoints.directional import _adapter_can_serve
            for sym in {a.underlying for a in active}:
                inst = registry.get_instrument(sym)
                if not inst:
                    continue
                if not _adapter_can_serve(inst, adapter_manager.get_data_source()):
                    continue

                try:
                    cached = _snap_cache.get(sym)
                    if cached:
                        # SSE already fetched this — reuse without exchange call
                        await _alert_svc.check_and_fire(
                            sym=sym,
                            spot_price=cached.spot_price,
                            ivr=cached.ivr,
                            green_arrow=cached.green_arrow,
                            red_arrow=cached.red_arrow,
                            current_state=cached.current_state,
                        )
                        continue

                    # Cache miss — UI not streaming; fetch fresh
                    spot = await ad.get_index_price(inst)
                    c4h = await ad.get_candles(inst, "4H", limit=200)
                    c1h = await ad.get_candles(inst, "1H", limit=400)
                    ivr = await compute_ivr(ad, inst, c1h)
                    _bg_mode = getattr(app.state, "trading_mode", None)
                    regime = compute_regime(
                        c4h,
                        macro_filter=_bg_mode.macro_filter if _bg_mode else "adx_4h",
                    )
                    signal = compute_signal(
                        c1h,
                        st_threshold=_bg_mode.st_threshold if _bg_mode else 3,
                    )
                    setup = evaluate_setup(regime, signal)

                    snap_kwargs = dict(
                        sym=sym,
                        spot_price=float(spot),
                        ivr=ivr,
                        green_arrow=signal.green_arrow,
                        red_arrow=signal.red_arrow,
                        current_state=setup.state.value,
                    )
                    _snap_cache.put(**snap_kwargs)
                    await _alert_svc.check_and_fire(**snap_kwargs)

                except Exception as exc:
                    log.debug("Background alert check failed for %s: %s", sym, exc)

        except Exception as exc:
            log.warning("Background alert checker error: %s", exc)


async def _background_position_monitor(app: FastAPI) -> None:
    """
    Auto-monitor all open positions on each mode's poll_interval_s.
    Runs TrailingStopEngine + check_exits for every active position;
    closes stopped-out positions and fires partial exits without user action.
    """
    import asyncio
    from app.services import paper_store as _ps
    from app.services.exchanges import instrument_registry as _reg
    from app.schemas.positions import PositionStatus
    from app.core.trading_mode import MODES, DEFAULT_MODE

    DEFAULT_INTERVAL = 60   # fallback when no mode is set

    while True:
        try:
            mode = getattr(app.state, "trading_mode", None)
            interval = mode.poll_interval_s if mode else DEFAULT_INTERVAL
        except Exception:
            interval = DEFAULT_INTERVAL

        await asyncio.sleep(interval)

        try:
            ad = adapter_manager.get_adapter()
            if not ad:
                continue
            active = [
                p for p in _ps.list_positions()
                if p.status.value in ("open", "partially_closed")
            ]
            if not active:
                continue

            from app.engines.directional.signal_engine import compute_signal
            from app.engines.directional.monitor_engine import check_exits
            from app.engines.directional.trailing_stop  import TrailState, TrailingStopEngine
            from app.schemas.risk import ExitSignal
            from app.api.v1.endpoints.config import get_runtime_risk
            from app.api.v1.endpoints.positions import _estimate_pnl, _dte_from_expiry
            from app.services import pnl_history as _pnl_history
            risk = get_runtime_risk()
            now_ms = int(time.time() * 1000) if 'time' in dir() else __import__('time').time_ns() // 1_000_000

            import asyncio as _aio
            sem = _aio.Semaphore(3)

            def _is_scalping(pos) -> bool:
                mode = getattr(pos, "mode", None) or ""
                notes = pos.notes or ""
                return mode == "scalping" or "SCALP" in notes

            async def _auto_monitor_one(pos):
                async with sem:
                    try:
                        inst = _reg.get_instrument(pos.underlying)
                        if not inst:
                            return

                        # ── Timeframe selection ──────────────────────────
                        # Scalping positions trail on 15m candles to avoid
                        # the 1H lag that stops out 15m entries before the
                        # trail can react.  Directional positions keep 1H.
                        is_scalp = _is_scalping(pos)
                        trail_tf = "15m" if is_scalp else "1H"

                        c_trail = await ad.get_candles(inst, trail_tf, limit=200)
                        signal = compute_signal(c_trail)
                        current_spot = await ad.get_index_price(inst)
                        leg = pos.sized_trade.structure.legs[0] if pos.sized_trade.structure.legs else None
                        dte_exp = _dte_from_expiry(leg.expiry_date) if leg else -1
                        if dte_exp >= 0:
                            current_dte = dte_exp
                        else:
                            elapsed = int((__import__('time').time() * 1000 - pos.entry_timestamp_ms) / 86_400_000)
                            current_dte = max(0, (leg.dte if leg else 0) - elapsed)

                        direction_sign = 1 if pos.sized_trade.structure.direction.value == "long" else -1
                        estimated_pnl  = _estimate_pnl(
                            pos.sized_trade,
                            current_spot - pos.entry_spot_price,
                            direction_sign,
                            pos.sized_trade.max_risk_usd,
                            pos.sized_trade.structure.max_gain,
                        )

                        # ── Tiered TP evaluation (scalping only) ────────
                        if is_scalp and pos.trail_stop_json and pos.status.value == "open":
                            try:
                                _ts = TrailState.from_json(pos.trail_stop_json)
                                _scalp_cfg = getattr(app.state, "scalping_config", None)
                                _tp_cfg = getattr(_scalp_cfg, "tiered_tp", None) if _scalp_cfg else None
                                if _tp_cfg and _tp_cfg.enabled and not _ts.tp1_triggered:
                                    _entry = pos.entry_price_real or pos.entry_spot_price
                                    _risk = abs(_entry - (pos.initial_sl or _entry * 0.95))
                                    if _risk > 0:
                                        if direction_sign == 1:
                                            _r_mult = (current_spot - _entry) / _risk
                                        else:
                                            _r_mult = (_entry - current_spot) / _risk
                                        if _r_mult >= _tp_cfg.tp1_r_multiple:
                                            _clip = pos.sized_trade.contracts * _tp_cfg.tp1_size_pct
                                            _clip = max(1, int(round(_clip)))
                                            log.info("🎯 TP1 triggered: %s at %.2fR — closing %d/%d contracts",
                                                     pos.underlying, _r_mult, _clip, pos.sized_trade.contracts)
                                            # Fire market reduce-only close (live positions only)
                                            if not pos.is_paper:
                                                _exec_side = "sell" if direction_sign == 1 else "buy"
                                                try:
                                                    from app.services import exchange_account_store as _ecs_tp
                                                    from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter as _DiaTp
                                                    _ac = _ecs_tp.get_active()
                                                    if _ac and _ac.api_key and not _ac.api_key.startswith("DUMMY"):
                                                        _base = (_ac.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
                                                        _live_ad = _DiaTp(api_key=_ac.api_key, api_secret=_ac.api_secret, is_paper=False, base_url=_base)
                                                        _delta = inst.delta_perp_symbol or f"{pos.underlying}USD"
                                                        _pid = await _live_ad.get_product_id(_delta)
                                                        await _live_ad.market_reduce_close(_pid, _exec_side, float(_clip))
                                                        log.info("TP1 market reduce-only order placed for %s: %d contracts", pos.underlying, _clip)
                                                except Exception as _pex:
                                                    log.warning("TP1 partial close failed for %s: %s", pos.id, _pex)
                                            # Book the partial close in paper_store & refresh
                                            _ps.partial_close_position(
                                                pos.id, float(current_spot), _tp_cfg.tp1_size_pct,
                                            )
                                            pos = _ps.get_position(pos.id) or pos
                                            # Mark TP1 triggered; pull stop to breakeven
                                            _ts.tp1_triggered = True
                                            if _tp_cfg.move_to_be_at_tp1:
                                                _ts.current_stop = round(_entry, 4)
                                                _ts.breakeven_set = True
                                                _ps.update_position(
                                                    pos.id,
                                                    current_sl=round(_entry, 4),
                                                    trail_stop_json=_ts.to_json(),
                                                )
                                                log.info("🛡️ Stop moved to breakeven (%.2f) for %s", _entry, pos.underlying)
                                            else:
                                                _ps.update_position(pos.id, trail_stop_json=_ts.to_json())
                            except Exception as _tpe:
                                log.debug("Tiered TP eval error for %s: %s", pos.id, _tpe)

                        # Trail update
                        if pos.trail_stop_json and pos.status.value in ("open", "partially_closed"):
                            try:
                                _ts = TrailState.from_json(pos.trail_stop_json)
                                _global_mode = getattr(app.state, "trading_mode", None) or MODES[DEFAULT_MODE]
                                _mo = MODES.get("scalping", _global_mode) if is_scalp else _global_mode
                                _dir = "bullish" if direction_sign == 1 else "bearish"
                                _st  = signal.st_values[0] if signal.st_values else 0.0
                                _tu  = TrailingStopEngine().update(
                                    state=_ts, candles=c_trail[-30:], st_value=_st,
                                    direction=_dir,
                                    entry_price=pos.entry_price_real or pos.entry_spot_price,
                                    mode=_mo, initial_tp=pos.initial_tp,
                                )
                                old_sl = pos.current_sl
                                _ps.update_position(
                                    pos.id,
                                    trail_stop_json=_ts.to_json(),
                                    current_sl=round(_tu.new_stop, 4),
                                    current_tp=pos.current_tp,
                                )

                                # ── Live stop amendment ──────────────────
                                # When the stop ratcheted AND this is a live
                                # non-paper position, push the new stop to
                                # the exchange via cancel+replace.
                                if (_tu.new_stop != old_sl and not pos.is_paper
                                        and pos.order_id and pos.order_status == "filled"):
                                    try:
                                        from app.services import exchange_account_store
                                        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
                                        active_cfg = exchange_account_store.get_active()
                                        if active_cfg and active_cfg.api_key and not active_cfg.api_key.startswith("DUMMY"):
                                            api_base = (active_cfg.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
                                            live_adapter = DeltaIndiaAdapter(
                                                api_key=active_cfg.api_key,
                                                api_secret=active_cfg.api_secret,
                                                is_paper=False,
                                                base_url=api_base,
                                            )
                                            product_id = await live_adapter.get_product_id(
                                                inst.delta_perp_symbol or f"{pos.underlying}USD"
                                            )
                                            await live_adapter.cancel_replace_stop(
                                                product_id=product_id,
                                                side="sell" if direction_sign == 1 else "buy",
                                                size=float(pos.sized_trade.contracts),
                                                old_stop=float(old_sl) if old_sl else 0.0,
                                                new_stop=round(float(_tu.new_stop), 2),
                                            )
                                            log.info("Auto-monitor: live stop amended %s — %.2f → %.2f",
                                                     pos.underlying, old_sl or 0, _tu.new_stop)
                                    except Exception as _le:
                                        log.warning("Auto-monitor: live stop amendment failed for %s: %s", pos.id, _le)

                                if _tu.stopped_out:
                                    _ps.close_position(pos.id, float(current_spot))
                                    log.info("Auto-monitor: trail stop hit for %s at %.2f", pos.id, current_spot)
                                    return
                                if _tu.partial and pos.status.value == "open":
                                    _pr = getattr(_tu.partial, "partial_ratio", 0.25)
                                    _ps.partial_close_position(pos.id, float(current_spot), _pr)
                            except Exception as _te:
                                log.debug("Auto-monitor trail error for %s: %s", pos.id, _te)

                        exit_sig = check_exits(
                            pos.sized_trade, signal, estimated_pnl, current_dte,
                            current_spot=float(current_spot),
                            current_tp=pos.current_tp,
                            current_sl=pos.current_sl,
                            force_exit_dte=inst.force_exit_dte,
                            financial_stop_pct=risk.financial_stop_pct,
                            partial_profit_r1=risk.partial_profit_r1,
                            partial_profit_r2=risk.partial_profit_r2,
                        )
                        _pnl_history.record(pos.id, current_spot, estimated_pnl, current_dte,
                                            int(__import__('time').time() * 1000))
                        if exit_sig.should_exit and not exit_sig.partial:
                            _ps.close_position(pos.id, float(current_spot))
                            log.info("Auto-monitor: %s closed (%s)", pos.id, exit_sig.exit_type)
                        elif exit_sig.partial and pos.status.value == "open":
                            _pr = getattr(exit_sig, "partial_ratio", 0.50)
                            _ps.partial_close_position(pos.id, float(current_spot), _pr)
                    except Exception as _e:
                        log.debug("Auto-monitor error for position %s: %s", pos.id, _e)

            await _aio.gather(*[_auto_monitor_one(p) for p in active], return_exceptions=True)
            log.debug("Auto-monitor: checked %d position(s)", len(active))

        except Exception as exc:
            log.warning("Background position monitor error: %s", exc)


async def _background_retry_worker(app: FastAPI, base_interval: int = 60) -> None:
    """
    Phase F: Drain live_safety._RETRY_QUEUE in the background.

    For each non-poison item: respect exponential backoff (60 s × 2^attempt,
    capped at 10 min), reconstruct minimal place_order from the saved payload,
    and either remove the item on success or mark_attempt on failure (which
    auto-flags poison after max_attempts).

    Brackets (SL/TP/trail) are intentionally NOT re-attached on retry. The
    payload only stores the minimum to identify the order; resending without
    brackets is the safer default — stops still come from the trail engine
    on every monitor tick.
    """
    import asyncio
    from app.services import live_safety, exchange_account_store
    from app.services.exchanges import instrument_registry as registry

    while True:
        await asyncio.sleep(base_interval)
        try:
            items = live_safety.list_retries(include_poison=False)
            if not items:
                continue

            active = exchange_account_store.get_active()
            if not active or not active.api_key or active.api_key.startswith("DUMMY"):
                continue

            from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
            api_base = (active.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
            adapter = DeltaIndiaAdapter(
                api_key=active.api_key, api_secret=active.api_secret,
                is_paper=False, base_url=api_base,
            )

            now_ms_outer = int(time.time() * 1000)
            for item in items:
                # Exponential backoff
                backoff_ms = min(60_000 * (2 ** item.attempt), 600_000)
                last_ts = item.last_attempt_ms or item.enqueued_ms
                if (now_ms_outer - last_ts) < backoff_ms:
                    continue

                payload = item.payload or {}
                sym = (payload.get("underlying") or "").upper()
                direction = payload.get("direction") or ""
                instrument_type = payload.get("instrument_type") or "futures"
                size = float(payload.get("size") or 1)
                leverage = float(payload.get("leverage") or 1)
                inst = registry.get_instrument(sym)
                if not inst:
                    live_safety.mark_attempt(item.id, "unknown_underlying")
                    continue

                # Re-check the safety gate before every retry
                from app.services import paper_store as _ps
                decision = live_safety.assert_safe_to_trade(
                    positions=_ps.list_positions(),
                )
                if not decision.allowed:
                    live_safety.mark_attempt(item.id, f"safety_gate:{decision.code}")
                    continue

                side = "buy" if direction == "long" else "sell"
                delta_symbol = inst.delta_perp_symbol or f"{sym}USD"
                try:
                    if instrument_type != "futures":
                        # Skip non-futures retries for now (manual flow handles them)
                        live_safety.mark_attempt(item.id, "non_futures_skipped")
                        continue
                    product_id = await adapter.get_product_id(delta_symbol)
                    try:
                        await adapter.set_leverage(product_id, leverage)
                    except Exception:
                        pass
                    order = await adapter.place_order(
                        symbol=delta_symbol, side=side, size=size,
                        order_type="market_order",
                    )
                    order_id = str(order.get("id") or order.get("order_id") or "")
                    if order_id:
                        idem = payload.get("client_order_id")
                        if idem:
                            live_safety.record_idempotency(idem, order_id)
                        live_safety.remove_retry(item.id)
                        log.info(
                            "RETRY succeeded for %s (%s): order_id=%s",
                            sym, item.id, order_id,
                        )
                    else:
                        live_safety.mark_attempt(item.id, "no_order_id_in_response")
                except Exception as exc:
                    live_safety.mark_attempt(item.id, str(exc))
                    log.warning(
                        "RETRY failed for %s (%s, attempt %d): %s",
                        sym, item.id, item.attempt + 1, exc,
                    )

        except Exception as exc:
            log.warning("Retry worker outer error: %s", exc)


_algo_last_ordered: dict[str, int] = {}   # key: "{sym}_{direction}" → timestamp_ms

def _algo_cooldown_ms(mode) -> int:
    """
    Cooldown = one typical trade hold duration for the active mode.
    Formula: max_hold_bars × poll_interval_s, floored at 15 min, capped at 24h.
      scalping:   15 bars ×  5s =   75s  → floor → 15 min
      intraday:   48 bars × 30s = 1440s  → 24 min
      swing:      42 bars ×300s = 12600s → 3.5h
      positional: 90 bars ×900s = 81000s → 22.5h
    """
    if not mode:
        return 60 * 60 * 1000  # 1h default
    raw_ms = mode.max_hold_bars * mode.poll_interval_s * 1000
    return max(15 * 60 * 1000, min(24 * 60 * 60 * 1000, raw_ms))

_ALGO_ACTIONABLE = frozenset({
    'ENTRY_ARMED_PULLBACK', 'ENTRY_ARMED_CONTINUATION',
    'CONFIRMED_SETUP_ACTIVE',
})


async def _auto_place_algo_order(app: FastAPI, sym: str, snap, mode) -> None:
    """
    Place a live order automatically when algo_mode is on and signal is actionable.

    Phase E: dispatches through OrderRouter so paper/shadow/live mode, correlation
    sizing, portfolio caps, microstructure veto, and retry-enqueue are uniform with
    the manual path.

    Composes all 5 P0 safety primitives:
      P0.1  live_safety.assert_safe_to_trade — kill switch, daily loss, idempotency
      P0.2  Score gate — signal_strength must be STRONG (≥75% confluence)
      P0.3  Risk-based sizing via size_trade() — respects RiskParams + scalp ceiling
      P0.4  v3 leverage scale via select_leverage(score, strength)
      P0.5  Idempotency record on successful fill (+ early skip on prior fill)
    """
    from app.services import exchange_account_store, live_safety, paper_store
    from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
    from app.services.exchanges import instrument_registry as registry
    from app.services.execution.order_router import (
        OrderRouter, RouterMode, OrderRouterRequest, RouterDeps,
    )
    from app.engines.directional.sizing_engine import size_trade
    from app.engines.directional.structure_selector import select_leverage
    from app.engines.risk import cooldown
    from app.schemas.execution import (
        TradeStructure, CandidateContract, Direction as ExecDir,
    )
    from app.schemas.risk import RiskParams
    from app.api.v1.endpoints.config import get_runtime_risk
    from app.api.v1.endpoints.trading import (
        LiveOrderRequest, _create_paper_tracking,
        _create_failed_algo_tracking, _send_order_telegram,
    )

    key = f"{sym}_{snap.direction}"
    now_ms = int(time.time() * 1000)

    # Per-(sym,direction) cooldown — independent of safety gate; prevents
    # back-to-back same-direction orders on every refresh tick.
    if now_ms - _algo_last_ordered.get(key, 0) < _algo_cooldown_ms(mode):
        return

    active = exchange_account_store.get_active()
    if not active or not active.api_key or active.api_key.startswith("DUMMY"):
        return

    inst = registry.get_instrument(sym)
    if not inst:
        return

    direction = snap.direction
    if direction not in ("long", "short"):
        return

    # ── P0.1: composite safety gate ────────────────────────────────────────
    decision = live_safety.assert_safe_to_trade(
        positions=paper_store.list_positions(),
    )
    if not decision.allowed:
        log.info("ALGO halted by safety gate: %s (%s)", decision.reason, decision.code)
        return

    # ── P0.2: score gate ───────────────────────────────────────────────────
    strength = getattr(snap, "signal_strength", "NONE")
    sig_score = float(getattr(snap, "signal_score", 0.0))
    score_for_lev = sig_score * 5.0   # 0-20 → 0-100
    if strength != "STRONG":
        log.debug("ALGO skip %s: strength=%s (need STRONG)", sym, strength)
        return

    # ── P0.4: leverage from v3 scale (must precede sizing) ─────────────────
    leverage = select_leverage(score=score_for_lev, signal_strength=strength)

    # SL/TP — same calculation as manual path
    spot = float(snap.spot_price or 0.0)
    if spot <= 0:
        return
    atr = float(snap.atr or spot * 0.02)
    stop_mult = mode.stop_atr_mult if mode else 2.0
    rr = mode.rr_target if mode else 2.0
    stop_dist = atr * stop_mult
    if direction == "long":
        stop_price = round(spot - stop_dist, 2)
        target_price = round(spot + stop_dist * rr, 2)
    else:
        stop_price = round(spot + stop_dist, 2)
        target_price = round(spot - stop_dist * rr, 2)

    # ── P0.3: risk-based sizing via size_trade() ───────────────────────────
    risk_params = get_runtime_risk()
    exec_dir = ExecDir.LONG if direction == "long" else ExecDir.SHORT
    sizing_leg = CandidateContract(
        instrument_name=f"{sym}-PERP", underlying=sym,
        strike=spot, expiry_date="", dte=0,
        option_type="futures",
        bid=0.0, ask=0.0, mark_price=spot, mid_price=spot,
        mark_iv=0.0,
        delta=1.0 if direction == "long" else -1.0,
        open_interest=0.0, volume_24h=0.0,
        spread_pct=0.0, health_score=0.0, healthy=True,
    )
    sizing_struct = TradeStructure(
        structure_type="futures",
        direction=exec_dir,
        legs=[sizing_leg],
        max_loss=stop_dist,
        max_gain=stop_dist * rr,
        net_premium=0.0,
        risk_reward=rr,
        score=score_for_lev,
        score_breakdown={},
        leverage=leverage,
        entry_price=spot,
    )
    sized = size_trade(sizing_struct, risk_params, leverage=leverage)
    order_size = float(sized.contracts)
    if order_size < 1:
        log.info("ALGO skip %s: sized contracts %s < 1", sym, order_size)
        return

    # ── P0.5: idempotency check (pre-flight) ───────────────────────────────
    minute_bucket = int(now_ms // 60_000)
    idem_key = live_safety.make_idempotency_key(
        sym, direction, "futures", order_size, minute_bucket, int(score_for_lev),
    )
    prior = live_safety.check_idempotency(idem_key)
    if prior:
        log.info("ALGO duplicate suppressed for %s: prior order %s", sym, prior)
        return

    # Reserve cooldown slot AFTER all gates so failed/skipped attempts retry.
    _algo_last_ordered[key] = now_ms

    # ── Phase E: build router and submit ───────────────────────────────────
    api_base = (active.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
    adapter = DeltaIndiaAdapter(
        api_key=active.api_key, api_secret=active.api_secret,
        is_paper=False, base_url=api_base,
    )

    router_mode_str = getattr(app.state, "algo_router_mode", "live") or "live"
    if not isinstance(router_mode_str, str):
        router_mode_str = "live"
    try:
        router_mode = RouterMode(router_mode_str)
    except (ValueError, TypeError):
        router_mode = RouterMode.LIVE

    correlation_tracker = getattr(app.state, "correlation_tracker", None)
    # Only honour the tracker when it's a real CorrelationTracker; MagicMock
    # leaks from test fixtures would otherwise return non-numeric penalties.
    try:
        from app.engines.analytics.correlation import CorrelationTracker as _CT
        if not isinstance(correlation_tracker, _CT):
            correlation_tracker = None
    except Exception:
        correlation_tracker = None

    def _list_open_positions():
        return [
            p for p in paper_store.list_positions()
            if getattr(p.status, "value", p.status) in ("open", "partially_closed")
        ]

    def _create_paper_position(req, exch_symbol, entry_price, order_id):
        body = LiveOrderRequest(
            underlying=req.underlying,
            direction=req.direction,
            instrument_type=req.instrument_type,
            size=req.size,
            leverage=req.leverage,
            order_type=req.order_type,
            stop_loss=req.stop_loss,
            take_profit=req.take_profit,
            notes=req.notes,
            client_order_id=req.client_order_id,
        )
        return _create_paper_tracking(
            body, req.underlying.upper(), float(entry_price),
            order_id or "", order_status="filled" if order_id else "open",
        )

    def _cooldown_blocked(sym_, mode_name, dir_, now_ms_):
        try:
            return cooldown.is_blocked(sym_, mode_name, dir_, now_ms_)
        except Exception:
            return False

    def _correlation_penalty(new_asset, open_positions):
        if not correlation_tracker:
            return 1.0
        try:
            assets = list({p.underlying for p in open_positions})
            return correlation_tracker.portfolio_correlation_penalty(new_asset, assets)
        except Exception:
            return 1.0

    def _portfolio_cap_breach(req, open_positions):
        return live_safety.per_symbol_cap_breach(req.underlying, open_positions)

    deps = RouterDeps(
        list_open_positions=_list_open_positions,
        create_paper_position=_create_paper_position,
        cooldown_blocked=_cooldown_blocked,
        correlation_penalty=_correlation_penalty,
        portfolio_cap_breach=_portfolio_cap_breach,
        microstructure_veto=lambda req: None,
    )
    router = OrderRouter(
        mode=router_mode, adapter=adapter, deps=deps,
        instrument_resolver=registry.get_instrument,
    )

    req = OrderRouterRequest(
        underlying=sym, direction=direction,
        instrument_type="futures",
        size=order_size, leverage=float(leverage),
        order_type="market",
        stop_loss=stop_price, take_profit=target_price,
        client_order_id=idem_key,
        score=score_for_lev,
        signal_strength=strength,
        mode_name=mode.name if mode else "swing",
        notes=f"[AUTO] {snap.current_state} score={score_for_lev:.0f} {strength}",
    )

    try:
        resp = await router.submit(req)
    except Exception as exc:
        log.error("ALGO router crashed for %s: %s", sym, exc)
        # Build a body for failed-tracking — same shape as before refactor.
        body = LiveOrderRequest(
            underlying=sym, direction=direction, instrument_type="futures",
            size=order_size, leverage=float(leverage), order_type="market",
            stop_loss=stop_price, take_profit=target_price,
            notes=req.notes, client_order_id=idem_key,
        )
        _create_failed_algo_tracking(body, sym, str(exc))
        _algo_last_ordered.pop(key, None)
        return

    if resp.accepted and resp.order_id:
        # Live or shadow fill — paper twin already created by router for shadow.
        body = LiveOrderRequest(
            underlying=sym, direction=direction, instrument_type="futures",
            size=order_size, leverage=float(leverage), order_type="market",
            stop_loss=stop_price, take_profit=target_price,
            notes=req.notes, client_order_id=idem_key,
        )
        _send_order_telegram(
            body, sym,
            "buy" if direction == "long" else "sell",
            resp.entry_price or spot, resp.order_id,
            "LIVE" if resp.mode == "live" else resp.mode.upper(),
        )
        log.info(
            "ALGO AUTO-ORDER [%s]: %s %s size=%.2f lev=%d score=%.0f @ %s order_id=%s",
            resp.mode.upper(), sym, direction.upper(), order_size, leverage,
            score_for_lev, resp.entry_price, resp.order_id,
        )
    elif resp.accepted and resp.paper_position_id:
        # Pure paper mode
        log.info(
            "ALGO PAPER: %s %s size=%.2f lev=%d pid=%s",
            sym, direction.upper(), order_size, leverage, resp.paper_position_id,
        )
    else:
        log.info(
            "ALGO router rejected %s: %s (%s)",
            sym, resp.reason, resp.code,
        )
        # Reset cooldown for retryable rejections so next signal tick can try.
        if resp.code in ("exchange_error", "no_adapter"):
            body = LiveOrderRequest(
                underlying=sym, direction=direction, instrument_type="futures",
                size=order_size, leverage=float(leverage), order_type="market",
                stop_loss=stop_price, take_profit=target_price,
                notes=req.notes, client_order_id=idem_key,
            )
            _create_failed_algo_tracking(body, sym, resp.reason or resp.code)
            _algo_last_ordered.pop(key, None)


async def _background_signal_refresher(app: FastAPI, interval: int = 30) -> None:
    """Refresh signals for all instruments every `interval` seconds. Runs immediately at startup."""
    import asyncio
    from app.api.v1.endpoints.directional import (
        _compute_signal_item, _adapter_can_serve,
        _save_signal_tracker_state,
    )
    from app.services.exchanges import instrument_registry as registry
    from app.services import snapshot_cache as _snap_cache

    while True:
        try:
            ad = adapter_manager.get_adapter()
            if not ad:
                await asyncio.sleep(interval)
                continue
            mode = getattr(app.state, "trading_mode", None)
            macro_filter = mode.macro_filter  if mode else "adx_4h"
            st_threshold = mode.st_threshold  if mode else 3
            stop_mult    = mode.stop_atr_mult if mode else 2.0
            rr_target    = mode.rr_target     if mode else 2.0
            current_source = adapter_manager.get_data_source()
            instruments = [
                inst for inst in registry.list_instruments()
                if _adapter_can_serve(inst, current_source)
            ]
            if instruments:
                results = await asyncio.gather(
                    *[_compute_signal_item(inst, ad, macro_filter, st_threshold, stop_mult, rr_target, mode=mode)
                      for inst in instruments],
                    return_exceptions=True,
                )
                ok = sum(1 for r in results if isinstance(r, dict) and r.get('fresh'))
                log.info("Signal refresh: %d/%d instruments updated", ok, len(instruments))

            # Persist tracker state so server restarts don't re-fire existing signals
            _save_signal_tracker_state()

            # Auto-order trigger: when algo_mode is on, auto-place orders for actionable signals
            if getattr(app.state, "algo_mode", False):
                for inst in instruments:
                    snap = _snap_cache.get(inst.underlying)
                    if not snap:
                        continue
                    if snap.current_state in _ALGO_ACTIONABLE and snap.direction != "neutral":
                        asyncio.create_task(
                            _auto_place_algo_order(app, inst.underlying, snap, mode)
                        )

        except Exception as exc:
            log.debug("Signal refresher error: %s", exc)
        await asyncio.sleep(interval)  # sleep at end so first run is immediate


async def _background_ohlcv_updater(interval_hours: int = 1) -> None:
    """Keeps OHLCV store fresh — runs immediately then every hour."""
    from app.services.delta_candle_fetcher import run_full_fetch
    while True:
        try:
            await run_full_fetch()
        except Exception as exc:
            log.warning("OHLCV background update error: %s", exc)
        await asyncio.sleep(interval_hours * 3600)


async def _broadcast_ofi(app: FastAPI) -> None:
    """
    Broadcasts Level 2 Order Flow Imbalance (OFI) to the active websocket channels.
    """
    import asyncio
    from app.api.v1.endpoints.stream import stream_manager
    from app.services.delta_l2_socket import l2_manager
    
    # Symbols to track/broadcast
    active_symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
    
    while True:
        await asyncio.sleep(0.5)
        try:
            for sym in active_symbols:
                ofi_val = l2_manager.get_ofi(sym)
                if ofi_val != 0:
                    await stream_manager.broadcast_to_channel(
                        sym,
                        {
                            "type": "metrics_update",
                            "symbol": sym,
                            "data": {"ofi": ofi_val}
                        }
                    )
        except Exception as exc:
            log.warning("OFI broadcaster error: %s", exc)


async def _background_vcp_live_feed(app: FastAPI) -> None:
    """
    VCP live execution feed — runs when algo_mode is on.

    Spawns one VCPLiveFeed per active VCP profile (BTC/ETH × 15m/30m).
    Each feed consumes the exchange WebSocket and drives VCPExecutor.on_bar()
    which submits orders through OrderRouter.

    The feed is resilient: on WebSocket disconnection it exponential-backoff
    reconnects up to 5× before giving up and signalling the executor to halt.
    """
    import asyncio
    from app.engines.hybrid_vcp import VCPLiveFeed, VCPFeedConfig, PROFILES
    from app.services import exchange_account_store
    from app.services.execution.order_router import OrderRouter, RouterMode, RouterDeps
    from app.services.exchanges import instrument_registry as registry
    from app.services import paper_store

    profiles_by_asset: dict[str, list[str]] = {
        "BTC": [
            "btc_scalping_5m", "btc_scalping_15m", "btc_scalping_30m",
            "btc_intraday_1h", "btc_intraday_4h",
        ],
        "ETH": [
            "eth_scalping_5m", "eth_scalping_15m", "eth_scalping_30m",
            "eth_intraday_1h",
        ],
    }

    feeds: dict[str, VCPLiveFeed] = {}
    routers: dict[str, OrderRouter] = {}
    active_feeds: list[asyncio.Task] = []

    def _make_router(profile_key: str, mode_str: str) -> OrderRouter:
        active = exchange_account_store.get_active() or type("A", (), {"api_key": "", "api_secret": "", "extra": {}})()
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        api_base = (active.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
        adapter = DeltaIndiaAdapter(
            api_key=active.api_key, api_secret=active.api_secret,
            is_paper=(mode_str == "paper"),
            base_url=api_base,
        )

        try:
            router_mode = RouterMode(mode_str)
        except Exception:
            router_mode = RouterMode.LIVE

        def _list_open_positions():
            return [
                p for p in paper_store.list_positions()
                if getattr(p.status, "value", p.status) in ("open", "partially_closed")
            ]

        def _cooldown_blocked(sym_, mode_name, dir_, now_ms_):
            from app.engines.risk import cooldown
            try:
                return cooldown.is_blocked(sym_, mode_name, dir_, now_ms_)
            except Exception:
                return False

        deps = RouterDeps(
            list_open_positions=_list_open_positions,
            create_paper_position=lambda *a, **k: None,
            cooldown_blocked=_cooldown_blocked,
            correlation_penalty=lambda *a, **k: 1.0,
            portfolio_cap_breach=lambda *a, **k: None,
            microstructure_veto=lambda *a, **k: None,
        )
        return OrderRouter(
            mode=router_mode, adapter=adapter, deps=deps,
            instrument_resolver=registry.get_instrument,
        )

    while True:
        # Re-evaluate every 30s so new feeds start if algo_mode toggles on mid-session
        await asyncio.sleep(30)

        try:
            algo_mode = getattr(app.state, "algo_mode", False)
            vcp_mode  = getattr(app.state, "vcp_mode_enabled", False)
            router_mode_str = getattr(app.state, "algo_router_mode", "live") or "live"

            # Both algo_mode AND vcp_mode must be on to start feeds
            if not algo_mode or not vcp_mode:
                # algo_mode off — stop all feeds gracefully
                for f in feeds.values():
                    await f.stop()
                feeds.clear()
                routers.clear()
                log.debug("VCP live feed: algo_mode off, feeds stopped")
                continue

            # Determine which profiles are in the active track set
            from app.engines.directional.track_selector import select_tracks
            active_profiles: set[str] = set()
            for asset, profile_keys in profiles_by_asset.items():
                for pk in profile_keys:
                    tracks = select_tracks(asset, pk)
                    if "vcp" in tracks:
                        active_profiles.add(pk)

            # Start feed for any new profile not yet running
            for profile_key in sorted(active_profiles):
                if profile_key in feeds:
                    continue
                profile = PROFILES.get(profile_key)
                if not profile:
                    continue

                # Get symbol mapping
                asset = "BTC" if "btc" in profile_key else "ETH"
                sym = f"{asset}USD"

                router = _make_router(profile_key, router_mode_str)
                routers[profile_key] = router

                adapter = router.adapter  # share the adapter with the feed

                tf_secs = profile.signal_bar_ms // 1000

                feed_cfg = VCPFeedConfig(
                    exchange="delta_india",
                    symbols=[sym],
                    signal_tf_secs=tf_secs,
                )

                from app.engines.hybrid_vcp import VCPExecutor, VCPExecutorConfig
                exec_cfg = VCPExecutorConfig(
                    vol_filter_pct=profile.vol_filter_pct,
                    flow_threshold=profile.flow_threshold,
                    max_ibs_long=profile.max_ibs_long,
                    min_ibs_short=profile.min_ibs_short,
                    max_rsi_long=profile.max_rsi_long,
                    min_rsi_short=profile.min_rsi_short,
                )
                executor = VCPExecutor(
                    profile=profile,
                    router=router,
                    adapter=adapter,
                    config=exec_cfg,
                )

                feed = VCPLiveFeed(config=feed_cfg, executor=executor)
                await feed.start()
                feeds[profile_key] = feed
                log.info(f"VCP live feed started: {profile_key} on {sym}")

                # Keep app.state in sync so the /vcp-mode endpoint reflects reality
                app.state.vcp_feed_count = len(feeds)
                app.state.vcp_active_profiles = sorted(feeds.keys())

        except Exception as exc:
            log.warning("VCP live feed background error: %s", exc)


async def _background_scalping_alerts(interval: int = 45) -> None:
    """Periodically scan scalping signals and push Telegram alerts for new ready
    setups. No-ops when Telegram isn't configured or alerts are toggled off."""
    from app.services.notifications import telegram_bot as _bot
    await asyncio.sleep(10)  # let startup settle before the first scan
    while True:
        try:
            await _bot.push_signal_alerts()
        except Exception as exc:
            log.debug("scalping alert push error: %s", exc)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    paper_store.bootstrap()
    exchange_account_store.bootstrap()
    _webhook_store_svc.bootstrap()
    _alert_store_bootstrap.bootstrap()
    _pnl_history_svc.bootstrap()
    from app.services import eval_history as _eval_history_svc
    _eval_history_svc.bootstrap()
    from app.services import arrow_store as _arrow_store_svc
    _arrow_store_svc.bootstrap()

    # Init OHLCV table and kick off first fetch in background (non-blocking)
    from app.services.ohlcv_store import init_ohlcv_table
    init_ohlcv_table()
    
    # --- V4 TimescaleDB / Postgres Bootstrap ---
    try:
        await init_db_schema()
        log.info("V4 Postgres schema bootstrap complete.")
    except Exception as e:
        log.warning(f"V4 Postgres bootstrap skipped (falling back to SQLite): {e}")

    # Restore signal tracker state — prevents re-firing Telegram on server restart
    from app.api.v1.endpoints.directional import _load_signal_tracker_state, _migrate_signal_ids_to_v2
    _load_signal_tracker_state()
    _migrate_signal_ids_to_v2()

    from app.core.trading_mode import MODES, DEFAULT_MODE
    from app.services.db import get_trading_mode, get_config
    mode_name = get_trading_mode() or DEFAULT_MODE
    if mode_name not in MODES:
        mode_name = DEFAULT_MODE
    app.state.trading_mode = MODES[mode_name]
    app.state.algo_mode = get_config("algo_mode", "false").lower() == "true"
    app.state.vcp_mode_enabled = get_config("vcp_mode", "false").lower() == "true"
    # Scoring strategy — controls how TF+VCP+MR are combined into a direction/score.
    # Persisted via db.set_config("scoring_strategy", ...). Default "by_edge_max_linear_agree".
    from app.engines.directional.track_scoring import set_strategy as _set_scoring_strategy
    _saved_strategy = get_config("scoring_strategy") or "by_edge_max_linear_agree"
    _set_scoring_strategy(_saved_strategy)
    # Phase F: paper / shadow / live router mode for the auto-trader.
    # Persisted via db.set_config("algo_router_mode", ...). Default "live"
    # preserves prior behaviour for users who already have algo configured.
    _router_mode = (get_config("algo_router_mode") or "live").lower()
    if _router_mode not in ("paper", "shadow", "live"):
        _router_mode = "live"
    app.state.algo_router_mode = _router_mode

    # Restore persisted Telegram credentials. They're saved to config by
    # PUT /config/telegram but the module only read env vars at import — so after
    # a restart Telegram silently went quiet (send() returns False with no token).
    try:
        import app.services.notifications.telegram as _tg_mod
        _tg_token = get_config("telegram_bot_token")
        _tg_chat  = get_config("telegram_chat_id")
        if _tg_token:
            _tg_mod.TELEGRAM_TOKEN = _tg_token
        if _tg_chat:
            _tg_mod.TELEGRAM_CHAT_ID = _tg_chat
        if get_config("telegram_verified") == "1":
            _tg_mod.TELEGRAM_REACHABLE = True
        log.info("Telegram config restored: token=%s chat=%s",
                 "set" if _tg_mod.TELEGRAM_TOKEN else "—",
                 "set" if _tg_mod.TELEGRAM_CHAT_ID else "—")
    except Exception as _e:
        log.warning("Telegram config restore skipped: %s", _e)

    # Restore persisted scalping config (survives server restarts)

    # Restore persisted StatArb config (survives server restarts)
    from app.engines.statarb.config import StatArbConfig as _SAC, default_statarb_config as _default_sac
    _saved_sac = get_config("statarb_config")
    if _saved_sac:
        try:
            cfg = _SAC.model_validate_json(_saved_sac)
            app.state.statarb_config = cfg
            log.info("Restored StatArb config from DB")
        except Exception:
            app.state.statarb_config = _default_sac()
    else:
        app.state.statarb_config = _default_sac()
    from app.engines.scalping.config import ScalpingConfig as _SC, default_config as _default_sc
    _saved_sc = get_config("scalping_config")
    if _saved_sc:
        try:
            cfg = _SC.model_validate_json(_saved_sc)
            if not cfg.profiles:
                cfg.profiles = _default_sc().profiles
            app.state.scalping_config = cfg
            log.info("Restored scalping config from DB")
        except Exception:
            app.state.scalping_config = _default_sc()
    else:
        app.state.scalping_config = _default_sc()

    # Restore persisted Telegram config (survives server restarts)
    from app.services.notifications import telegram as _telegram_svc
    saved_tg_token = get_config("telegram_bot_token")
    saved_tg_chat  = get_config("telegram_chat_id")
    if saved_tg_token:
        _telegram_svc.TELEGRAM_TOKEN   = saved_tg_token
    if saved_tg_chat:
        _telegram_svc.TELEGRAM_CHAT_ID = saved_tg_chat
    # Restore verified status from DB — no network call needed at startup.
    # telegram_verified is written to DB whenever a test message succeeds.
    if saved_tg_token and saved_tg_chat:
        if get_config("telegram_verified") == "1":
            _telegram_svc.TELEGRAM_REACHABLE = True
            log.info("Telegram: restored verified status from DB")

    from app.services.execution.circuit_breaker import CircuitBreaker
    app.state.circuit_breaker = CircuitBreaker(telegram=_telegram_svc)

    # v3 singletons
    from app.engines.risk.circuit_breaker import DrawdownCircuitBreaker, CircuitBreakerConfig
    from app.engines.analytics.correlation import CorrelationTracker
    from app.services.calibration import CalibrationService
    from app.services import db as _db

    dd_cfg = CircuitBreakerConfig(
        warn_dd=float(os.environ.get('STERLING_DD_WARN', '0.05')),
        halt_dd=float(os.environ.get('STERLING_DD_HALT', '0.10')),
        reset_dd=float(os.environ.get('STERLING_DD_RESET', '0.15')),
    )
    app.state.dd_circuit_breaker = DrawdownCircuitBreaker(dd_cfg, portfolio_value=100_000.0)
    app.state.correlation_tracker = CorrelationTracker(assets=['BTC', 'ETH', 'SOL'])
    app.state.calibration_service = CalibrationService(db_path=_db._DB_PATH)

    # Build market data adapter (use pre-injected adapter in tests, else build fresh)
    if not getattr(app.state, "adapter", None):
        exchange = settings.exchange_adapter.lower()
        # If active exchange config has keys, use them for data adapters that need auth
        active_cfg = exchange_account_store.get_active()
        api_key = active_cfg.api_key if active_cfg and active_cfg.name == exchange else ""
        api_secret = active_cfg.api_secret if active_cfg and active_cfg.name == exchange else ""
        ad = await adapter_manager.init(exchange, api_key, api_secret)
        app.state.adapter = ad
    else:
        # Tests inject adapter — sync adapter_manager so it matches
        adapter_manager._adapter = app.state.adapter
        adapter_manager._data_source = settings.exchange_adapter.lower()

    from app.services.exchanges import instrument_registry as registry
    ad = adapter_manager.get_adapter()
    reachable = await ad.ping()
    active_ex = exchange_account_store.get_active()
    log.info(
        "Sterling v0.4 | env=%s | data=%s [%s] | account=%s | instruments=%d | positions=%d",
        settings.environment,
        adapter_manager.get_data_source(),
        "OK" if reachable else "UNREACHABLE",
        active_ex.display_name if active_ex else "none",
        len(registry.list_instruments()),
        len(paper_store.list_positions()),
    )
    if not reachable:
        log.warning("Market data exchange unreachable at startup — will retry on request")

    import asyncio
    bg_task = asyncio.create_task(_background_alert_checker(app, interval=30))
    log.info("Background alert checker started (every 30s)")
    # Phase: faster signal cadence — default 5 s. Env-tunable via
    # STERLING_SIGNAL_INTERVAL_S so deployments with tighter exchange rate
    # limits can dial it back.
    try:
        signal_interval = int(os.environ.get("STERLING_SIGNAL_INTERVAL_S", "5"))
    except (TypeError, ValueError):
        signal_interval = 5
    signal_interval = max(1, min(60, signal_interval))
    signal_refresh_task = asyncio.create_task(
        _background_signal_refresher(app, interval=signal_interval)
    )
    log.info("Background signal refresher started (every %ss)", signal_interval)
    position_monitor_task = asyncio.create_task(_background_position_monitor(app))
    log.info("Background position monitor started (interval=mode.poll_interval_s)")
    retry_worker_task = asyncio.create_task(_background_retry_worker(app, base_interval=60))
    log.info("Background retry worker started (every 60s + exponential backoff)")
    ohlcv_task = asyncio.create_task(_background_ohlcv_updater(interval_hours=1))
    log.info("OHLCV background updater started (hourly)")
    ofi_broadcast_task = asyncio.create_task(_broadcast_ofi(app))
    log.info("OFI Broadcaster started (every 0.5s)")

    # ── VCP Live Feed ─────────────────────────────────────────────────────────
    # Start the Hybrid VCP-Momentum live execution feed when algo_mode is on.
    # The feed connects to the exchange WebSocket, reconstructs signal bars,
    # and drives VCPExecutor.on_bar() → OrderRouter for each completed bar.
    vcp_feed_task = asyncio.create_task(_background_vcp_live_feed(app))
    log.info("VCP Live Feed task started")
    statarb_task = asyncio.create_task(_background_statarb_trader(app, interval=15))
    log.info("StatArb background trader started")

    # ── Telegram bot + signal-detection alerts ────────────────────────────────
    from app.services.notifications import telegram_bot as _tg_bot
    tg_bot_task = asyncio.create_task(_tg_bot.poll_loop())
    tg_alert_task = asyncio.create_task(_background_scalping_alerts(interval=45))
    log.info("Telegram bot + signal alerts started")

    yield

    for _t in (tg_bot_task, tg_alert_task):
        _t.cancel()
        try:
            await _t
        except (Exception, BaseException):
            pass

    ofi_broadcast_task.cancel()
    try:
        await ofi_broadcast_task
    except (Exception, BaseException):
        pass

    statarb_task.cancel()
    try:
        await statarb_task
    except (Exception, BaseException):
        pass
    vcp_feed_task.cancel()
    try:
        await vcp_feed_task
    except (Exception, BaseException):
        pass

    ohlcv_task.cancel()
    try:
        await ohlcv_task
    except (Exception, BaseException):
        pass
    bg_task.cancel()
    try:
        await bg_task
    except (Exception, BaseException):
        pass
    signal_refresh_task.cancel()
    try:
        await signal_refresh_task
    except (Exception, BaseException):
        pass
    position_monitor_task.cancel()
    try:
        await position_monitor_task
    except (Exception, BaseException):
        pass
    retry_worker_task.cancel()
    try:
        await retry_worker_task
    except (Exception, BaseException):
        pass
    await adapter_manager.close_current()
    log.info("Sterling shutdown complete")


async def _background_statarb_trader(app: FastAPI, interval: int = 15) -> None:
    """Periodically scans for StatArb signals and executes them if auto_trade is enabled."""
    import asyncio
    import time
    from app.engines.statarb.scanner import scan_statarb_universe
    from app.services import ohlcv_store, paper_store, exchange_account_store
    from app.schemas.market import Candle
    from app.services.execution.order_router import OrderRouter, RouterMode, RouterDeps, OrderRouterRequest
    from app.services.exchanges import instrument_registry as registry
    from app.api.v1.endpoints.trading import LiveOrderRequest, _create_paper_tracking

    while True:
        await asyncio.sleep(interval)
        try:
            cfg = getattr(app.state, "statarb_config", None)
            if not cfg or not cfg.enabled or not getattr(cfg, "auto_trade", False):
                continue
                
            # Fetch candles for assets
            assets_to_fetch = set()
            for p in cfg.pairs:
                if getattr(p, "enabled", True):
                    assets_to_fetch.add(p.asset_x)
                    assets_to_fetch.add(p.asset_y)
                    if getattr(p, "asset_z", None):
                        assets_to_fetch.add(p.asset_z)
            
            if not assets_to_fetch:
                continue

            data_dict = {cfg.timeframe: {}}
            now_sec = int(time.time())
            # Lookback enough days depending on timeframe
            since = now_sec - (30 * 24 * 60 * 60)
            
            for symbol in assets_to_fetch:
                try:
                    rows = ohlcv_store.get_candles(symbol, cfg.timeframe, limit=2000, since=since)
                    if rows:
                        from app.services.delta_l2_socket import l2_manager
                        candles = [
                            Candle(
                                timestamp_ms=int(r["time"]) * 1000, 
                                open=r["open"], 
                                high=r["high"], 
                                low=r["low"], 
                                close=r["close"],
                                volume=r["volume"], 
                                is_closed=True
                            ) for r in rows
                        ]
                        
                        best_bid = l2_manager.best_bid.get(symbol)
                        best_ask = l2_manager.best_ask.get(symbol)
                        if best_bid and best_ask:
                            mid_price = (best_bid[0] + best_ask[0]) / 2.0
                            candles.append(Candle(
                                timestamp_ms=int(time.time() * 1000),
                                open=mid_price, high=mid_price, low=mid_price, close=mid_price,
                                volume=0.0, is_closed=False
                            ))
                        data_dict[cfg.timeframe][symbol] = candles
                except Exception:
                    pass
            
            res = scan_statarb_universe(data_dict, cfg)
            
            # Setup router
            active = exchange_account_store.get_active()
            if not active or not active.api_key or active.api_key.startswith("DUMMY"):
                continue
            
            from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
            api_base = (active.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
            adapter = DeltaIndiaAdapter(
                api_key=active.api_key, api_secret=active.api_secret,
                is_paper=False, base_url=api_base,
            )

            router_mode_str = getattr(app.state, "algo_router_mode", "live") or "live"
            try:
                router_mode = RouterMode(router_mode_str)
            except Exception:
                router_mode = RouterMode.LIVE

            def _list_open_positions():
                return [p for p in paper_store.list_positions() if getattr(p.status, "value", p.status) in ("open", "partially_closed")]

            def _create_paper_position(req, exch_symbol, entry_price, order_id):
                body = LiveOrderRequest(
                    underlying=req.underlying, direction=req.direction, instrument_type=req.instrument_type,
                    size=req.size, leverage=req.leverage, order_type=req.order_type,
                    stop_loss=req.stop_loss, take_profit=req.take_profit, notes=req.notes, client_order_id=req.client_order_id,
                )
                return _create_paper_tracking(
                    body, req.underlying.upper(), float(entry_price),
                    order_id or "", order_status="filled" if order_id else "open",
                )
                
            deps = RouterDeps(
                list_open_positions=_list_open_positions,
                create_paper_position=_create_paper_position,
                cooldown_blocked=lambda *a, **k: False,
                correlation_penalty=lambda *a, **k: 1.0,
                portfolio_cap_breach=lambda *a, **k: None,
                microstructure_veto=lambda req: None,
            )
            
            router = OrderRouter(mode=router_mode, adapter=adapter, deps=deps, instrument_resolver=registry.get_instrument)
            
            # Very simple idempotent execution based on signal state
            for sig in res.signals:
                if sig.action in ("ENTRY_LONG", "ENTRY_SHORT"):
                    log.info("StatArb Auto-Trade triggered for %s: %s (Z=%.2f)", sig.pair_name, sig.action, sig.current_z)
                    
                    # Need to place 2 or 3 orders depending on pair legs.
                    # This is simplified for demonstration of the hook.
                    # We just execute Leg Y and Leg X in opposite directions.
                    
                    dir_y = "long" if sig.action == "ENTRY_LONG" else "short"
                    dir_x = "short" if sig.action == "ENTRY_LONG" else "long"
                    
                    # Execute leg Y
                    now_ms = int(time.time() * 1000)
                    req_y = OrderRouterRequest(
                        underlying=sig.asset_y.replace("USDT", "").replace("USD", ""),
                        direction=dir_y, instrument_type="futures",
                        size=sig.suggested_size_y, leverage=1.0, order_type="market",
                        notes=f"[STATARB] {sig.pair_name} Leg Y", client_order_id=f"statarb_{sig.pair_name}_{now_ms}_y"
                    )
                    
                    # Execute leg X
                    req_x = OrderRouterRequest(
                        underlying=sig.asset_x.replace("USDT", "").replace("USD", ""),
                        direction=dir_x, instrument_type="futures",
                        size=sig.suggested_size_x, leverage=1.0, order_type="market",
                        notes=f"[STATARB] {sig.pair_name} Leg X", client_order_id=f"statarb_{sig.pair_name}_{now_ms}_x"
                    )
                    
                    try:
                        await router.submit(req_y)
                        await router.submit(req_x)
                    except Exception as e:
                        log.error("StatArb Router failed: %s", e)
                        
        except Exception as exc:
            log.warning("StatArb auto-trader error: %s", exc)

def create_app() -> FastAPI:
    app = FastAPI(
        title="Sterling",
        description="Universal crypto options platform — paper trading, engine-driven",
        version="0.4.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # CSP: API-only server — no scripts/styles served
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        return response

    app.include_router(health_router)
    app.include_router(instruments_router, prefix="/api/v1")
    app.include_router(directional_router, prefix="/api/v1")
    app.include_router(positions_router, prefix="/api/v1")
    app.include_router(config_router, prefix="/api/v1")
    app.include_router(backtest_router, prefix="/api/v1")
    app.include_router(exchanges_router, prefix="/api/v1")
    app.include_router(account_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")
    app.include_router(webhooks_router, prefix="/api/v1")
    app.include_router(options_router, prefix="/api/v1")
    app.include_router(stats_router, prefix="/api/v1")
    app.include_router(session_router, prefix="/api/v1")
    app.include_router(trading_mode_router, prefix="/api/v1")
    app.include_router(candles_router, prefix="/api/v1")
    app.include_router(ohlcv_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(analytics_baseline_router, prefix="/api/v1")
    app.include_router(risk_dashboard_router, prefix="/api/v1")
    app.include_router(trading_router, prefix="/api/v1")

    # Triple SuperTrend strategy (self-contained module)
    from app.api.v1.endpoints.strategy import router as strategy_router
    app.include_router(strategy_router, prefix="/api/v1")

    # Scalping strategies (Price Action / SMC / MA Crossover)
    from app.api.v1.endpoints.scalping import router as scalping_router
    app.include_router(scalping_router, prefix="/api/v1")
    
    from app.api.v1.endpoints.statarb import router as statarb_router
    app.include_router(statarb_router, prefix="/api/v1/statarb", tags=["statarb"])

    # V4 WebSocket Manager Router
    from app.api.v1.endpoints import stream
    app.include_router(stream.router, prefix="/api/v1/stream", tags=["stream"])

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
