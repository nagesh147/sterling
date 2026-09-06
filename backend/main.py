import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
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
from app.api.v1.endpoints.derivatives import router as derivatives_router
from app.api.v1.endpoints.ohlcv import router as ohlcv_router
from app.api.v1.endpoints.wfo import router as wfo_router
from app.api.v1.endpoints.vectorized_backtest import router as vectorized_backtest_router
import secrets
from app.core.csp import reset_csp_nonce, set_csp_nonce
from app.api.v1.endpoints.sterling_v2 import router as sterling_v2_router
from app.api.v1.endpoints.paper import router as paper_router
from app.services import alert_store as _alert_store_svc

log = get_logger(__name__)


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


# ─── Derivatives scanner + auto-execute ─────────────────────────────────
#
# Scanner body lives in app/services/derivatives_scanner.py so the unit
# tests can drive `auto_execute_derivative` + `run_scanner_tick`
# without booting the full ASGI lifespan. Main.py keeps only the loop
# that drives the tick every `interval` seconds.


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
    # Adopt KITE_API_KEY / KITE_API_SECRET (and optionally KITE_ACCESS_TOKEN) from
    # the environment so a fresh DB or a new machine boots already provisioned —
    # no retyping credentials into the UI before anything works.
    try:
        from app.services.exchanges.kite import auth as _kite_auth
        _kite_auth.seed_from_env()
    except Exception as exc:  # noqa: BLE001
        log.warning("Kite env seeding skipped: %s", exc)
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

    log.info("Startup complete")

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
    # The ping used to be skipped whenever the crypto kill switch was off, which
    # left an Indian-only build reporting its data source as "PAUSED" forever.
    reachable = await ad.ping()
    reach_str = "OK" if reachable else "UNREACHABLE"
    active_ex = exchange_account_store.get_active()
    log.info(
        "Sterling v0.4 | env=%s | data=%s [%s] | account=%s | instruments=%d | positions=%d",
        settings.environment,
        adapter_manager.get_data_source(),
        reach_str,
        active_ex.display_name if active_ex else "none",
        len(registry.list_instruments()),
        len(paper_store.list_positions()),
    )
    if reachable is False:
        log.warning("Market data exchange unreachable at startup — will retry on request")

    import asyncio

    # Kite tick stream: restart it if its task dies.
    #
    # The stream's own reconnect loop handles a dropped socket. This covers the
    # case that loop cannot: the task itself finishing. `ticker_manager.ensure()`
    # repairs that, but only when something calls it, and its only caller is a
    # subscribe — which the frontend issues when its token set changes. An
    # operator watching a board of live prices changes nothing, so nothing
    # triggered the repair and every price sat on the 30-second REST heartbeat
    # looking alive.
    from app.services.exchanges.kite import ticker_manager as _kite_ticker_manager
    ticker_watchdog_task = asyncio.create_task(_kite_ticker_manager.supervise(interval=30))
    log.info("Kite ticker watchdog started (every 30s)")

    # ATM Premium Imbalance: arm inside the pre-open lead so both legs are
    # subscribed before the bell. Arming does not trade -- entry is still gated
    # on verified market hours -- and the loop is a no-op whenever the strategy
    # is disabled or unsized, which is the default.
    from app.services.atm_premium_imbalance_runner import auto_arm_loop
    atm_auto_arm_task = asyncio.create_task(auto_arm_loop(interval=30))

    # Gamma Move: levels -> strikes -> trigger, on the strategy's own cadence.
    # The loop is a no-op while the strategy is disabled, which is its default.
    # The loop reconciles against the broker before its first scan, so a restart
    # cannot open a second position in a contract it already holds.
    from app.services.gamma_move_runner import auto_scan_loop as _gamma_move_scan
    gamma_move_task = asyncio.create_task(_gamma_move_scan(interval=300))

    # OI Wall Flow: universe -> one expiry chain -> classify, on the strategy's
    # own cadence. The loop is a no-op while the strategy is disabled. It
    # reconciles against the broker before its first scan, so a restart cannot
    # open a second position in a contract it already holds.
    from app.services.oi_wall_flow_runner import auto_scan_loop as _oi_wall_flow_scan
    oi_wall_flow_task = asyncio.create_task(_oi_wall_flow_scan(interval=300))

    # Adaptive Edge: underlyings -> contracts -> candidates, on a faster cadence
    # because the source is a scalping strategy. Safe to run unconditionally:
    # the loop is a no-op outside the session window, and the strategy's
    # promotion gate refuses live execution regardless of the account's
    # paper/live setting, so this scans and paper-trades but cannot reach real
    # money until somebody promotes it deliberately.
    from app.services.adaptive_edge_runner import auto_scan_loop as _adaptive_edge_scan
    adaptive_edge_task = asyncio.create_task(_adaptive_edge_scan(interval=60))

    log.info("ATM PI auto-arm loop started (every 30s)")
    log.info("Adaptive Edge auto scan loop started (every 60s)")

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

    # Kite session keeper — renews access tokens shortly before the 06:00 IST reset
    # for accounts Zerodha issued a refresh_token to. The strategy engines run
    # headless, so without this a token that lapses overnight leaves the 09:15
    # scans sessionless until someone opens the UI.
    from app.services.exchanges.kite.auth import session_keeper_loop as _kite_session_keeper
    kite_session_task = asyncio.create_task(_kite_session_keeper())
    log.info("Kite session keeper started (every 10 min)")

    # Sterling Value-Flow Navigator — independent strategy scanner. It reuses
    # the Kite account/client/instrument caches, but does not depend on the
    # Triple-Supertrend engine being enabled or scanning.
    from app.services.navigator.runtime import auto_scan_loop as _navigator_auto_scan
    navigator_task = asyncio.create_task(_navigator_auto_scan())
    log.info("Value-Flow Navigator auto-scan loop started (every 5 min)")

    # ── Telegram bot + Kite signal alerts ────────────────────────────────────
    from app.services.notifications import telegram_bot as _tg_bot
    tg_bot_task = asyncio.create_task(_tg_bot.poll_loop())
    tg_kite_alert_task = asyncio.create_task(_background_kite_alerts(interval=60))
    log.info("Telegram bot + Kite signal alerts started")

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

    for _t in (tg_bot_task, tg_kite_alert_task):
        _t.cancel()
        try:
            await _t
        except (Exception, BaseException):
            pass

    kite_engine_task.cancel()
    try:
        await kite_engine_task
    except (Exception, BaseException):
        pass
    kite_session_task.cancel()
    try:
        await kite_session_task
    except (Exception, BaseException):
        pass
    navigator_task.cancel()
    try:
        await navigator_task
    except (Exception, BaseException):
        pass
    atm_auto_arm_task.cancel()
    try:
        await atm_auto_arm_task
    except (Exception, BaseException):
        pass
    gamma_move_task.cancel()
    try:
        await gamma_move_task
    except (Exception, BaseException):
        pass
    oi_wall_flow_task.cancel()
    try:
        await oi_wall_flow_task
    except (Exception, BaseException):
        pass

    adaptive_edge_task.cancel()
    try:
        await adaptive_edge_task
    except (Exception, BaseException):
        pass
    ticker_watchdog_task.cancel()
    try:
        await ticker_watchdog_task
    except asyncio.CancelledError:
        pass

    await adapter_manager.close_current()
    log.info("Sterling shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sterling",
        description="Indian markets options platform — paper trading, engine-driven",
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
        # Minted BEFORE the handler runs so the handler can stamp it on the tags
        # it emits. A nonce the page never sees is a nonce that blocks the page.
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce
        _nonce_token = set_csp_nonce(nonce)
        try:
            response = await call_next(request)
        finally:
            reset_correlation_id(_cid_token)
            reset_csp_nonce(_nonce_token)
        response.headers["X-Correlation-ID"] = cid
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # CSP.
        #
        # `default-src 'none'` is right for the API and wrong for the one route
        # that serves a page: the Kite callback. That page is a self-contained
        # HTML document with an inline stylesheet and an inline script, and this
        # header silently blocked both — so it rendered as unstyled user-agent
        # defaults, AND its handoff script never ran. That script is what tells
        # the open Sterling tab the session arrived; without it the app looked
        # like the login had failed, which is what sent people to copy the
        # request_token out of the URL and paste it — a token already spent by
        # the callback, so it could only ever be rejected. One header, the whole
        # symptom.
        #
        # An HTML response therefore gets a nonce rather than `unsafe-inline`:
        # the page's own style and script run, and injected ones still cannot.
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Content-Security-Policy"] = (
                f"default-src 'none'; style-src 'nonce-{nonce}'; "
                f"script-src 'nonce-{nonce}'; img-src data:; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            )
        else:
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
    app.include_router(derivatives_router, prefix="/api/v1")
    app.include_router(sterling_v2_router, prefix="/api/v1")

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

    # Advisory 09:15 same-minute relative-volume leader scanner.
    from app.api.v1.endpoints.opening_volume_leaders import router as opening_volume_leaders_router
    app.include_router(opening_volume_leaders_router, prefix="/api/v1")

    from app.api.v1.endpoints.adaptive_edge import router as adaptive_edge_router
    app.include_router(adaptive_edge_router, prefix="/api/v1")

    # Offline market-data lake (kitelake). Storage is relocatable — typically a removable
    # drive — so these endpoints report an absent volume as data, never as an error.
    from app.api.v1.endpoints.datalake import router as datalake_router
    app.include_router(datalake_router, prefix="/api/v1")

    from app.api.v1.endpoints.pcr import router as pcr_router
    app.include_router(pcr_router, prefix="/api/v1")

    from app.api.v1.endpoints.bear_to_bearish import router as bear_to_bearish_router
    app.include_router(bear_to_bearish_router, prefix="/api/v1")

    from app.api.v1.endpoints.simulation import router as simulation_router
    app.include_router(simulation_router, prefix="/api/v1")

    return app


app = create_app()

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
