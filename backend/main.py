import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.async_tasks import spawn_background
from app.core.observability import (
    configure_json_logging, new_correlation_id, set_correlation_id, reset_correlation_id,
)
from app.services import paper_store
from app.services import exchange_account_store
from app.services import adapter_manager
from app.services import webhook_store as _webhook_store_svc
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
from app.api.v1.endpoints.derivatives import router as derivatives_router
from app.api.v1.endpoints.ohlcv import router as ohlcv_router
from app.api.v1.endpoints.wfo import router as wfo_router
from app.api.v1.endpoints.vectorized_backtest import router as vectorized_backtest_router
from app.api.v1.endpoints.sterling_v2 import router as sterling_v2_router
from app.api.v1.endpoints.paper import router as paper_router
from app.services import alert_store as _alert_store_svc

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
            if not getattr(app.state, "scalp_mode", False):
                continue
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
            if not getattr(app.state, "scalp_mode", False):
                continue
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
            from app.engines.directional.trailing_stop  import TrailState, TrailingStopEngine, realistic_stop_fill
            from app.engines.risk import options_monitor as _opt_mon
            from app.api.v1.endpoints.config import get_runtime_risk
            from app.api.v1.endpoints.positions import _estimate_pnl, _dte_from_expiry
            from app.services import pnl_history as _pnl_history
            risk = get_runtime_risk()
            now_ms = int(time.time() * 1000) if 'time' in dir() else __import__('time').time_ns() // 1_000_000

            import asyncio as _aio
            sem = _aio.Semaphore(3)

            # Phase 1: one option-chain fetch per underlying per polling
            # cycle, shared across every open options position. The
            # Semaphore(3) bottleneck on per-position fetches stalled
            # scalping positions at 5s cadence when >10 options were open.
            chain_cache = _opt_mon.OptionChainCache()

            # Resolve the active trading mode once so we can drive DTE
            # force-close windows per its `force_close_minutes_before_expiry`.
            _force_close_min = getattr(
                getattr(app.state, "trading_mode", None) or MODES[DEFAULT_MODE],
                "force_close_minutes_before_expiry", 120,
            )

            def _is_scalping(pos) -> bool:
                mode = getattr(pos, "mode", None) or ""
                notes = pos.notes or ""
                return mode == "scalping" or "SCALP" in notes

            async def _auto_monitor_one(pos):
                async with sem:
                    try:
                        # ── Instrument-type discriminator ─────────────────
                        # Phase 1 of the derivatives build implements the
                        # options branch: per-underlying chain caching,
                        # staleness gate, DTE force-close, microstructure
                        # veto on amend, premium-aware close PnL. Futures
                        # path behavior is unchanged.
                        _structure = pos.sized_trade.structure
                        is_options = _structure.structure_type != "futures"

                        inst = _reg.get_instrument(pos.underlying)
                        if not inst:
                            return

                        # ── Options-only setup ────────────────────────────
                        # Fetch chain (or use cached), locate this position's
                        # option, set up the close-kwargs builder and
                        # microstructure-veto helper. Falls back gracefully
                        # to spot-based monitoring when chain is unavailable
                        # — Phase 0 behavior — so a one-poll fetch failure
                        # doesn't crash the monitor.
                        chain_option = None
                        chain_age_ms = -1
                        if is_options:
                            cache_entry = await chain_cache.get_or_fetch(
                                pos.underlying, ad, _reg,
                            )
                            if cache_entry is not None:
                                chain, chain_fetch_ts = cache_entry
                                chain_age_ms = now_ms - chain_fetch_ts
                                leg0 = pos.sized_trade.structure.legs[0] if pos.sized_trade.structure.legs else None
                                if leg0 is not None:
                                    chain_option = _opt_mon.find_option(chain, leg0.instrument_name)
                                if _opt_mon.is_chain_stale(chain_fetch_ts, now_ms):
                                    log.debug(
                                        "monitor[%s]: chain stale (%dms > 30000ms); skipping Greek-dependent updates",
                                        pos.id, chain_age_ms,
                                    )
                                    chain_option = None      # treat stale as unavailable

                        # ── Timeframe selection ──────────────────────────
                        # Scalping positions trail on 15m candles to avoid
                        # the 1H lag that stops out 15m entries before the
                        # trail can react.  Directional positions keep 1H.
                        is_scalp = _is_scalping(pos)
                        trail_tf = "15m" if is_scalp else "1H"

                        c_trail = await ad.get_candles(inst, trail_tf, limit=200)
                        signal = compute_signal(c_trail)
                        current_spot = await ad.get_index_price(inst)

                        # ── Phase 1: DTE force-close ─────────────────────
                        # Run BEFORE trail/exit logic so an expiring options
                        # position never wastes a cycle trying to ratchet a
                        # stop that's about to settle. Tiered by notional
                        # inside should_force_close: > $1k → 120 min window,
                        # else 30 min. settlement_recorded flag is True only
                        # when we crossed actual expiry — distinguishes a
                        # pre-expiry market-close from a cash-settle event
                        # for after-tax PnL accounting.
                        if is_options and pos.status.value in ("open", "partially_closed"):
                            should_fc, fc_reason = _opt_mon.should_force_close(
                                pos, _force_close_min, now_ms,
                            )
                            if should_fc:
                                at_settlement = _opt_mon.is_at_settlement(pos, now_ms)
                                # If LIVE non-paper, fire the market reduce-close on the exchange.
                                if not pos.is_paper and pos.order_id and pos.order_status == "filled":
                                    try:
                                        from app.services import exchange_account_store as _ecs_fc
                                        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter as _DiaFc
                                        _ac = _ecs_fc.get_active()
                                        if _ac and _ac.api_key and not _ac.api_key.startswith("DUMMY"):
                                            _base = (_ac.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
                                            _live_ad = _DiaFc(api_key=_ac.api_key, api_secret=_ac.api_secret, is_paper=False, base_url=_base)
                                            leg0 = pos.sized_trade.structure.legs[0] if pos.sized_trade.structure.legs else None
                                            if leg0:
                                                _pid = await _live_ad.get_product_id(leg0.instrument_name)
                                                # Side for closing a long option = sell (we only buy options today)
                                                await _live_ad.market_reduce_close(
                                                    _pid, "sell", float(pos.sized_trade.contracts),
                                                )
                                                log.info("Force-close market reduce placed for %s: %s", pos.id, fc_reason)
                                    except Exception as _fce:
                                        log.warning("Force-close live order failed for %s: %s", pos.id, _fce)
                                # Book the close in paper_store with premium + settlement attribution.
                                _close_kw = _opt_mon.option_close_kwargs(
                                    chain_option, at_settlement, "force_close_dte",
                                )
                                _ps.close_position(pos.id, float(current_spot), **_close_kw)
                                log.info("Auto-monitor: force-closed %s (%s, settlement=%s)",
                                         pos.id, fc_reason, at_settlement)
                                return
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
                                _scalp_cfg = getattr(app.state, "sterling_engine_config", None)
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
                                # the exchange via cancel+replace. Phase 1
                                # adds the microstructure veto for options:
                                # if the current option spread is wider than
                                # 8% of mid, defer the amend by one poll —
                                # otherwise the carrier order fills against
                                # a synthetic mid that's 10-20% off the true
                                # price on illiquid strikes.
                                if (_tu.new_stop != old_sl and not pos.is_paper
                                        and pos.order_id and pos.order_status == "filled"):
                                    veto_amend = False
                                    if is_options and chain_option is not None:
                                        veto_amend, veto_reason = _opt_mon.should_veto_amend(chain_option)
                                        if veto_amend:
                                            log.info(
                                                "Auto-monitor: amend deferred for %s (%s) — will retry next poll",
                                                pos.id, veto_reason,
                                            )
                                    if not veto_amend:
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
                                                # Options use the option's instrument_name; futures use the perp symbol.
                                                if is_options:
                                                    leg0 = pos.sized_trade.structure.legs[0] if pos.sized_trade.structure.legs else None
                                                    _amend_symbol = leg0.instrument_name if leg0 else None
                                                    # Long-option close side is always "sell" (we only buy options today).
                                                    _amend_side = "sell"
                                                else:
                                                    _amend_symbol = inst.delta_perp_symbol or f"{pos.underlying}USD"
                                                    _amend_side = "sell" if direction_sign == 1 else "buy"
                                                if _amend_symbol:
                                                    product_id = await live_adapter.get_product_id(_amend_symbol)
                                                    await live_adapter.cancel_replace_stop(
                                                        product_id=product_id,
                                                        side=_amend_side,
                                                        size=float(pos.sized_trade.contracts),
                                                        old_stop=float(old_sl) if old_sl else 0.0,
                                                        new_stop=round(float(_tu.new_stop), 2),
                                                    )
                                                    log.info("Auto-monitor: live stop amended %s — %.2f → %.2f",
                                                             pos.underlying, old_sl or 0, _tu.new_stop)
                                        except Exception as _le:
                                            log.warning("Auto-monitor: live stop amendment failed for %s: %s", pos.id, _le)

                                if _tu.stopped_out:
                                    # Fill at ~the stop, NOT the poll-time spot.
                                    # The monitor polls on an interval, so a
                                    # breach is seen after price has run past the
                                    # stop; booking that overshoot charged the
                                    # whole interval's drift as slippage and turned
                                    # breakeven stops into large losses. Model a
                                    # real stop fill (stop ± a few bps).
                                    _stop_px = float(_tu.new_stop) if _tu.new_stop else float(current_spot)
                                    _exit_px = realistic_stop_fill(_stop_px, float(current_spot), direction_sign)
                                    # Premium-aware close: when chain_option
                                    # is present, pass its mark_price as
                                    # exit_premium so the realised options
                                    # PnL is correct. Falls back to the
                                    # delta-linear estimate (with logged
                                    # warning) when chain is stale/missing.
                                    if is_options:
                                        _close_kw = _opt_mon.option_close_kwargs(
                                            chain_option,
                                            _opt_mon.is_at_settlement(pos, now_ms),
                                            "trail",
                                        )
                                        _ps.close_position(pos.id, float(current_spot), **_close_kw)
                                    else:
                                        _ps.close_position(
                                            pos.id, _exit_px,
                                            exit_reason="trail",
                                        )
                                    log.info("Auto-monitor: trail stop hit for %s — fill %.4f (stop %.4f, spot %.4f)",
                                             pos.id, _exit_px, _stop_px, current_spot)
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
                            # Same premium-aware exit logic as the trail
                            # close — options use exit_premium from current
                            # chain, futures use the spot-linear formula.
                            if is_options:
                                _sig_close_kw = _opt_mon.option_close_kwargs(
                                    chain_option,
                                    _opt_mon.is_at_settlement(pos, now_ms),
                                    f"signal:{exit_sig.exit_type}",
                                )
                                _ps.close_position(pos.id, float(current_spot), **_sig_close_kw)
                            else:
                                _ps.close_position(
                                    pos.id, float(current_spot),
                                    exit_reason=f"signal:{exit_sig.exit_type}",
                                )
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
            if not getattr(app.state, "scalp_mode", False):
                continue
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
                    except Exception as _exc:
                        log.debug("suppressed: %s", _exc)
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


def _build_greeks_budget_gate(app: FastAPI):
    """Build the async `greeks_budget_gate` callable wired into every
    OrderRouter construction. Reads `app.state.greeks_budget_checker` at
    call time so a later update to the checker (e.g. NAV change) takes
    effect on the next order without rebuilding the router. Resolves the
    live adapter from `app.state.adapter` and uses it for option-chain
    fetches when an options order arrives. Returns a no-op callable when
    no checker is bound (early-boot or tests).
    """
    from app.engines.risk import portfolio_greeks_aggregator as _agg
    from app.services.exchanges import instrument_registry as _reg

    async def _gate(req, open_positions):
        checker = getattr(app.state, "greeks_budget_checker", None)
        if checker is None or checker.pv <= 0:
            return None
        adapter = getattr(app.state, "adapter", None)
        if adapter is None:
            return None

        async def _get_spot(sym: str) -> float:
            inst = _reg.get_instrument(sym)
            if inst is None:
                return 0.0
            try:
                return float(await adapter.get_index_price(inst))
            except Exception:
                return 0.0

        return await _agg.check_against_budget(
            req=req, open_positions=open_positions,
            adapter=adapter, checker=checker, get_spot=_get_spot,
        )

    return _gate


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
        greeks_budget_gate=_build_greeks_budget_gate(app),
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
        log.exception("ALGO router crashed for %s: %s", sym, exc)
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
            if not getattr(app.state, "scalp_mode", False):
                await asyncio.sleep(interval)
                continue
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

                from app.api.v1.endpoints.stream import stream_manager
                import time
                for r in results:
                    if isinstance(r, dict) and r.get('fresh'):
                        s = r.get('signal', {})
                        dsr = s.get('exec_confidence', 0)
                        wfa = s.get('signal_score', 0)
                        strength = s.get('signal_strength', 'NONE')
                        if dsr > 0.5 or strength == 'STRONG':
                            sym = s.get('sym', 'UNKNOWN')
                            strat = s.get('strategy', 'legacy')
                            msg = f"[PASS] {sym} {strat} (DSR: {dsr:.2f}, WFA: {wfa:.2f})"
                            async def _broadcast_log(m=msg, strngth=strength):
                                try:
                                    level = "INFO"
                                    if strngth == "STRONG": level = "INFO"
                                    elif strngth == "MODERATE": level = "WARNING"
                                    elif strngth == "WEAK": level = "ERROR"
                                    await stream_manager.broadcast_to_channel("arbitrator_logs", {
                                        "type": "log",
                                        "level": level,
                                        "message": m
                                    })
                                except Exception as _exc:
                                    log.debug("suppressed: %s", _exc)
                            spawn_background(_broadcast_log(), name="arbitrator-log")

            # Persist tracker state so server restarts don't re-fire existing signals
            _save_signal_tracker_state()

            # Auto-order trigger removed to allow frontend components (GrokSignalPane/ScalpingTab) to handle their own execution

        except Exception as exc:
            log.debug("Signal refresher error: %s", exc)
        await asyncio.sleep(interval)  # sleep at end so first run is immediate


# ─── Derivatives scanner + auto-execute ─────────────────────────────────
#
# Scanner body lives in app/services/derivatives_scanner.py so the unit
# tests can drive `auto_execute_derivative` + `run_scanner_tick`
# without booting the full ASGI lifespan. Main.py keeps only the loop
# that drives the tick every `interval` seconds.


async def _background_derivatives_scanner(app: FastAPI, interval: int = 30) -> None:
    """Loop driving `run_scanner_tick` every `interval` seconds. The
    scanner caches futures+options rows on app.state.derivatives_scan_cache
    and auto-fires candidates when `algo_mode` + per-strategy
    `auto_execute_<leg>` are both ON."""
    import asyncio
    from app.services.derivatives_scanner import run_scanner_tick

    while True:
        try:
            if getattr(app.state, "scalp_mode", False):
                await run_scanner_tick(app, interval_s=interval)
        except Exception as exc:
            import traceback
            log.warning("DERIV scanner outer error: %s\n%s", exc, traceback.format_exc())
        await asyncio.sleep(interval)


async def _background_ohlcv_updater(interval_hours: int = 1) -> None:
    """Keeps OHLCV store fresh — runs immediately then every hour."""
    import asyncio
    from app.services.delta_candle_fetcher import run_full_fetch
    while True:
        try:
            if getattr(app.state, "scalp_mode", False):
                await run_full_fetch()
        except Exception as exc:
            log.warning("OHLCV background update error: %s", exc)
        await asyncio.sleep(interval_hours * 3600)


async def _background_1m_updater(interval_min: int = 5) -> None:
    """Keep the 1-minute store fresh for core symbols — runs immediately then
    every `interval_min`. 1m is excluded from the hourly all-symbol fetch (too
    heavy across every product), so without this dedicated loop the 1m store
    silently freezes. Tight cadence keeps it ~real-time."""
    import asyncio
    from app.services.delta_candle_fetcher import fetch_core_1m
    while True:
        try:
            if getattr(app.state, "scalp_mode", False):
                await fetch_core_1m()
        except Exception as exc:
            log.warning("1m OHLCV background update error: %s", exc)
        await asyncio.sleep(interval_min * 60)


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
            if not getattr(app.state, "scalp_mode", False):
                continue
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
            greeks_budget_gate=_build_greeks_budget_gate(app),
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
            scalp_mode = getattr(app.state, "scalp_mode", False)
            vcp_mode  = getattr(app.state, "vcp_mode_enabled", False)
            router_mode_str = getattr(app.state, "algo_router_mode", "live") or "live"

            # Both algo_mode AND vcp_mode must be on to start feeds
            if not algo_mode or not vcp_mode or not scalp_mode:
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


async def _background_scalping_alerts(app: FastAPI, interval: int = 45) -> None:
    """Periodically scan scalping signals and push Telegram alerts for new ready
    setups. Skips entirely when scalp_mode is off."""
    import asyncio
    from app.services.notifications import telegram_bot as _bot
    await asyncio.sleep(10)  # let startup settle before the first scan
    while True:
        try:
            if getattr(app.state, "scalp_mode", False):
                await _bot.push_signal_alerts()
        except Exception as exc:
            log.debug("scalping alert push error: %s", exc)
        await asyncio.sleep(interval)


async def _background_kite_alerts(interval: int = 60) -> None:
    """Push NEW active Kite engine signals to Telegram — a SEPARATE stream from the
    crypto scalping alerts. Gated on market hours; the push itself no-ops unless a
    bot token/chat is configured and alerts are enabled."""
    import asyncio
    from app.services.notifications import telegram_kite as _kbot
    from app.services.kite_engine.market_hours import is_market_open
    await asyncio.sleep(12)
    while True:
        try:
            if is_market_open():
                await _kbot.push_kite_alerts()
        except Exception as exc:  # noqa: BLE001
            log.debug("kite alert push error: %s", exc)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    configure_json_logging()  # no-op unless settings.log_json (Phase 2 observability)
    paper_store.bootstrap()
    exchange_account_store.bootstrap()
    from app.services.exchanges.kite import accounts as _kite_accounts
    _kite_accounts.bootstrap()
    _webhook_store_svc.bootstrap()
    _alert_store_svc.bootstrap()
    _pnl_history_svc.bootstrap()
    from app.services import eval_history as _eval_history_svc
    _eval_history_svc.bootstrap()
    from app.services import arrow_store as _arrow_store_svc
    _arrow_store_svc.bootstrap()

    # Init OHLCV table and kick off first fetch in background (non-blocking)
    from app.services.ohlcv_store import init_ohlcv_table
    init_ohlcv_table()
    
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
    app.state.scalp_mode = get_config("scalp_mode", "false").lower() == "true"
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

    # Phase: derivatives_profiles and DailyLossConfig persistence loading
    try:
        from app.services.db import get_config
        import json
        
        dl_str = get_config("daily_loss_config")
        if dl_str:
            from app.services.live_safety import configure_daily_loss
            parsed = json.loads(dl_str)
            from app.services.live_safety import DailyLossConfig
            configure_daily_loss(DailyLossConfig(enabled=parsed.get("enabled", True), soft_warn_usd=parsed.get("soft_warn_usd", -500.0), hard_halt_usd=parsed.get("hard_halt_usd", -1500.0)))
            
        dp_str = get_config("derivatives_profiles")
        if dp_str:
            from app.engines.derivatives.schemas import StrategyDerivativesProfile
            parsed = json.loads(dp_str)
            restored = {}
            for k, v in parsed.items():
                restored[k] = StrategyDerivativesProfile(**v)
            app.state.derivatives_profile_overrides = restored
            log.info(f"Restored derivatives_profiles from DB for {list(restored.keys())}")
    except Exception as e:
        log.warning(f"Failed to restore configs from DB: {e}")

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
    from app.engines.sterling_engine.config import ScalpingConfig as _SC, default_config as _default_sc
    # New key, falling back to the legacy "scalping_config" for pre-rename installs.
    _saved_sc = get_config("sterling_engine_config") or get_config("scalping_config")
    if _saved_sc:
        try:
            cfg = _SC.model_validate_json(_saved_sc)
            if not cfg.profiles:
                cfg.profiles = _default_sc().profiles
            app.state.sterling_engine_config = cfg
            log.info("Restored scalping config from DB")
        except Exception:
            app.state.sterling_engine_config = _default_sc()
    else:
        app.state.sterling_engine_config = _default_sc()

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

    # Portfolio Greeks budget hard gate (Phase 0 of the derivatives build).
    # Read by `OrderRouter._submit_live` via the `greeks_budget_gate` dep
    # wired in `_router_deps_with_greeks_gate()` below. Bound to the same
    # NAV figure as `dd_circuit_breaker` so a single env knob moves both;
    # both should be kept in sync with actual account NAV in production.
    from app.engines.risk.greeks_budget import GreeksBudgetChecker, GreeksBudget
    app.state.greeks_budget_checker = GreeksBudgetChecker(
        GreeksBudget(), portfolio_value=100_000.0,
    )

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
    ohlcv_1m_task = asyncio.create_task(_background_1m_updater(interval_min=5))
    log.info("OHLCV 1m updater started (every 5 min, core symbols)")
    ofi_broadcast_task = asyncio.create_task(_broadcast_ofi(app))
    log.info("OFI Broadcaster started (every 0.5s)")

    # Arbitrator fake log worker for UI parity — only runs when crypto is on
    if app.state.scalp_mode:
        from app.api.v1.endpoints.stream import _arbitrator_log_worker
        arbitrator_log_task = asyncio.create_task(_arbitrator_log_worker())
        log.info("Arbitrator log worker started")
    else:
        arbitrator_log_task = None
        log.info("scalp_mode OFF — Arbitrator log worker NOT started")


    # ── VCP Live Feed ─────────────────────────────────────────────────────────
    # Start the Hybrid VCP-Momentum live execution feed when algo_mode is on.
    # The feed connects to the exchange WebSocket, reconstructs signal bars,
    # and drives VCPExecutor.on_bar() → OrderRouter for each completed bar.
    vcp_feed_task = asyncio.create_task(_background_vcp_live_feed(app))
    log.info("VCP Live Feed task started")

    # Derivatives scanner — populates /derivatives/scan cache and auto-fires
    # candidates when `algo_mode` + per-strategy `auto_execute_<type>` are on.
    deriv_scan_task = asyncio.create_task(_background_derivatives_scanner(app, interval=30))
    log.info("Derivatives scanner started (every 30s)")

    # Kite Sterling Kite Engine — background auto-scan of connected Kite
    # accounts (advisory by default; gated auto-exec when the user enables it).
    # First reconcile each account's auto-open guard against the broker's real
    # positions: the guard is DB-persisted across restarts, but a position may
    # have closed/expired while we were down — reconciling prevents both a stale
    # guard (forever-blocked re-entry) and a dropped guard (double-entry).
    from app.services.kite_engine.service import (
        auto_scan_loop as _kite_auto_scan,
        reconcile_all_auto_open as _kite_reconcile_auto_open,
    )
    try:
        await _kite_reconcile_auto_open()
    except Exception as exc:  # noqa: BLE001
        log.warning("Kite auto-open startup reconcile failed: %s", exc)
    kite_engine_task = asyncio.create_task(_kite_auto_scan())
    log.info("Kite Sterling Kite Engine auto-scan loop started (every 5 min)")

    # Sterling Value-Flow Navigator — independent strategy scanner. It reuses
    # the Kite account/client/instrument caches, but does not depend on the
    # Triple-Supertrend engine being enabled or scanning.
    from app.services.navigator.runtime import auto_scan_loop as _navigator_auto_scan
    navigator_task = asyncio.create_task(_navigator_auto_scan())
    log.info("Value-Flow Navigator auto-scan loop started (every 5 min)")

    # Real-time Delta options IV stream + recorder (Component ① of realtime-iv-stream).
    # Only starts when scalp_mode (crypto kill switch) is enabled.
    if app.state.scalp_mode:
        try:
            from app.services.delta_iv_socket import iv_manager
            from app.services.delta_iv_recorder import start_recorder
            from app.services.delta_l2_socket import l2_manager
            iv_manager.start()
            start_recorder()
            l2_manager.start()
            log.info("Delta real-time IV stream, recorder, and L2 socket started")
        except Exception:
            log.warning("Delta IV stream start failed (ws may be unreachable) — retry on next restart")
    else:
        log.info("scalp_mode OFF — Delta IV stream, recorder, and L2 socket NOT started")

    # ── Telegram bot + signal-detection alerts ────────────────────────────────
    from app.services.notifications import telegram_bot as _tg_bot
    tg_bot_task = asyncio.create_task(_tg_bot.poll_loop())
    tg_alert_task = asyncio.create_task(_background_scalping_alerts(app, interval=45))
    tg_kite_alert_task = asyncio.create_task(_background_kite_alerts(interval=60))
    log.info("Telegram bot + signal alerts started (crypto + kite)")

    # ── Live event bus + agents (Phase 3) — only when enable_event_bus is set ──
    from app.core.config import settings as _settings
    if getattr(_settings, "enable_event_bus", False):
        try:
            from app.bus.event_bus import EventBus
            from app.agents import PNLAgent, ReconciliationAgent, Orchestrator
            from app.services import event_emit
            _bus = EventBus()
            _pnl_agent = PNLAgent(bus=_bus)
            _recon_agent = ReconciliationAgent(bus=_bus)
            _orchestrator = Orchestrator(bus=_bus, heartbeat_interval=60.0)
            event_emit.configure(_bus, {
                "pnl": _pnl_agent, "reconciliation": _recon_agent,
                "orchestrator": _orchestrator,
            })
            app.state.event_bus = _bus
            app.state.pnl_agent = _pnl_agent
            app.state.orchestrator = _orchestrator
            await _orchestrator.start()
            log.info("Live event bus + agents started (PNL/Reconciliation, heartbeat 60s)")
        except Exception as exc:
            log.warning("event bus startup failed (non-fatal): %s", exc)

    yield

    try:
        _orch = getattr(app.state, "orchestrator", None)
        if _orch is not None:
            await _orch.stop()
        from app.services import event_emit as _ee
        _ee.reset()
    except Exception as _exc:
        log.debug("suppressed: %s", _exc)

    for _t in (tg_bot_task, tg_alert_task, tg_kite_alert_task):
        _t.cancel()
        try:
            await _t
        except (Exception, BaseException):
            pass

    if arbitrator_log_task is not None:
        arbitrator_log_task.cancel()
        try:
            await arbitrator_log_task
        except (Exception, BaseException):
            pass

    ofi_broadcast_task.cancel()
    try:
        await ofi_broadcast_task
    except (Exception, BaseException):
        pass

    deriv_scan_task.cancel()
    try:
        await deriv_scan_task
    except (Exception, BaseException):
        pass
    kite_engine_task.cancel()
    try:
        await kite_engine_task
    except (Exception, BaseException):
        pass
    navigator_task.cancel()
    try:
        await navigator_task
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
    ohlcv_1m_task.cancel()
    try:
        await ohlcv_1m_task
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
    try:
        from app.services.delta_iv_recorder import stop_recorder
        from app.services.delta_iv_socket import iv_manager
        from app.services.delta_l2_socket import l2_manager
        stop_recorder()
        iv_manager.stop()
        l2_manager.stop()
    except Exception as exc:
        log.warning("Error stopping IV stream/recorder/L2: %s", exc)

    await adapter_manager.close_current()
    log.info("Sterling shutdown complete")


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
        # Correlation id: honor an inbound one or mint a fresh id, bind it for
        # the request's logging context, and echo it back. (Phase 2 observability)
        cid = request.headers.get("X-Correlation-ID") or new_correlation_id()
        _cid_token = set_correlation_id(cid)
        try:
            response = await call_next(request)
        finally:
            reset_correlation_id(_cid_token)
        response.headers["X-Correlation-ID"] = cid
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # CSP: API-only server — no scripts/styles served
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        return response

    app.include_router(health_router)
    # More-specific stream prefix before generic /api/v1 routers (registration order).
    from app.api.v1.endpoints import stream
    app.include_router(stream.router, prefix="/api/v1/stream", tags=["stream"])

    app.include_router(instruments_router, prefix="/api/v1")
    app.include_router(paper_router, prefix="/api/v1")
    app.include_router(directional_router, prefix="/api/v1")
    app.include_router(positions_router, prefix="/api/v1")
    app.include_router(config_router, prefix="/api/v1")
    app.include_router(backtest_router, prefix="/api/v1")
    app.include_router(vectorized_backtest_router, prefix="/api/v1")
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
    app.include_router(wfo_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(analytics_baseline_router, prefix="/api/v1")
    app.include_router(risk_dashboard_router, prefix="/api/v1")
    app.include_router(trading_router, prefix="/api/v1")
    app.include_router(derivatives_router, prefix="/api/v1")
    app.include_router(sterling_v2_router, prefix="/api/v1")

    # Grok config
    from app.api.v1.endpoints.grok import router as grok_router
    app.include_router(grok_router, prefix="/api/v1")

    # Scalping strategies (Price Action / SMC / MA Crossover)
    from app.api.v1.endpoints.sterling_engine import router as sterling_engine_router
    app.include_router(sterling_engine_router, prefix="/api/v1")
    
    # Zerodha Kite (Indian markets) — multi-tenant manual console
    from app.api.v1.endpoints.kite import router as kite_router
    app.include_router(kite_router, prefix="/api/v1")

    # TrueData market data provider endpoints
    from app.api.v1.endpoints.truedata import router as truedata_router
    app.include_router(truedata_router, prefix="/api/v1")

    # Kite-exclusive Sterling Kite Engine options engine (scanner + advisory/auto-exec)
    from app.api.v1.endpoints.kite_engine import router as kite_engine_router
    app.include_router(kite_engine_router, prefix="/api/v1")

    # Kite-specific Telegram alert targets (per-user, separate from crypto bot)
    from app.api.v1.endpoints.kite_telegram import router as kite_telegram_router
    app.include_router(kite_telegram_router, prefix="/api/v1")

    # Sterling Value-Flow Navigator (Kite-only, off by default)
    from app.api.v1.endpoints.navigator import router as navigator_router
    app.include_router(navigator_router, prefix="/api/v1")

    from app.api.v1.endpoints.adaptive_edge import router as adaptive_edge_router
    app.include_router(adaptive_edge_router, prefix="/api/v1")

    # Offline market-data lake (kitelake). Storage is relocatable — typically a removable
    # drive — so these endpoints report an absent volume as data, never as an error.
    from app.api.v1.endpoints.datalake import router as datalake_router
    app.include_router(datalake_router, prefix="/api/v1")

    return app


app = create_app()

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
