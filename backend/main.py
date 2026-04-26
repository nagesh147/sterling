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
from app.services import alert_store as _alert_store_svc

log = get_logger(__name__)


async def _background_alert_checker(app: FastAPI, interval: int = 300) -> None:
    """Check alerts every `interval` seconds in the background."""
    import asyncio
    from app.engines.directional.regime_engine import compute_regime
    from app.engines.directional.signal_engine import compute_signal
    from app.engines.directional.setup_engine import evaluate_setup
    from app.engines.directional.orchestrator import compute_ivr
    from app.services.exchanges import instrument_registry as registry

    while True:
        await asyncio.sleep(interval)
        try:
            ad = adapter_manager.get_adapter()
            if not ad:
                continue

            for a in _alert_store_svc.list_alerts():
                _alert_store_svc.rearm_if_cooldown_elapsed(a.id)

            active = [a for a in _alert_store_svc.list_alerts() if a.status.value == "active"]
            if not active:
                continue

            for sym in {a.underlying for a in active}:
                inst = registry.get_instrument(sym)
                if not inst:
                    continue
                try:
                    spot = await ad.get_index_price(inst)
                    ivr = await compute_ivr(ad, inst)
                    c4h = await ad.get_candles(inst, "4H", limit=100)
                    c1h = await ad.get_candles(inst, "1H", limit=200)
                    regime = compute_regime(c4h)
                    signal = compute_signal(c1h)
                    setup = evaluate_setup(regime, signal)
                    for alert in active:
                        if alert.underlying != sym:
                            continue
                        result = _alert_store_svc.check_alert(
                            alert, spot_price=float(spot), ivr=ivr,
                            green_arrow=signal.green_arrow, red_arrow=signal.red_arrow,
                            current_state=setup.state.value,
                        )
                        if result.triggered:
                            _alert_store_svc.fire_alert(alert.id, trigger_value=result.current_value)
                            from app.services import webhook_store
                            await webhook_store.deliver_all(
                                f"{sym} Alert: {alert.condition.value}", result.message,
                                {"underlying": sym, "value": result.current_value}
                            )
                            log.info("Background alert fired: %s %s", alert.id, result.message)
                except Exception as exc:
                    log.debug("Background alert check failed for %s: %s", sym, exc)
        except Exception as exc:
            log.warning("Background alert checker error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    paper_store.bootstrap()
    exchange_account_store.bootstrap()
    _webhook_store_svc.bootstrap()
    _alert_store_bootstrap.bootstrap()

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
    bg_task = asyncio.create_task(_background_alert_checker(app, interval=300))
    log.info("Background alert checker started (every 300s)")

    yield

    bg_task.cancel()
    try:
        await bg_task
    except (Exception, BaseException):
        pass
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

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
