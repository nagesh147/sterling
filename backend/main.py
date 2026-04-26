from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.services.cache import CachingAdapter
from app.services.retry import RetryingAdapter
from app.services import paper_store
from app.services import exchange_account_store
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
            adapter = getattr(app.state, "adapter", None)
            if not adapter:
                continue

            # Rearm expired cooldowns
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
                    spot = await adapter.get_index_price(inst)
                    ivr = await compute_ivr(adapter, inst)
                    c4h = await adapter.get_candles(inst, "4H", limit=100)
                    c1h = await adapter.get_candles(inst, "1H", limit=200)
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
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("Background alert checker error: %s", exc)


def _build_raw_adapter():
    if settings.exchange_adapter.lower() == "okx":
        from app.services.exchanges.adapters.okx import OKXAdapter
        log.info("Market data: OKX")
        return OKXAdapter()
    if settings.exchange_adapter.lower() == "delta_india":
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        log.info("Market data: Delta Exchange India")
        return DeltaIndiaAdapter(is_paper=True)
    if settings.exchange_adapter.lower() == "binance":
        from app.services.exchanges.adapters.binance import BinanceAdapter
        log.info("Market data: Binance USDT-M Futures")
        return BinanceAdapter(is_paper=True)
    from app.services.exchanges.adapters.deribit import DeribitAdapter
    log.info("Market data: Deribit")
    return DeribitAdapter(base_url=settings.deribit_base_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    paper_store.bootstrap()
    exchange_account_store.bootstrap()

    if not getattr(app.state, "adapter", None):
        raw = _build_raw_adapter()
        app.state.adapter = CachingAdapter(RetryingAdapter(raw))

    adapter = app.state.adapter
    from app.services.exchanges import instrument_registry as registry
    reachable = await adapter.ping()
    active_ex = exchange_account_store.get_active()
    log.info(
        "Sterling v0.3 | env=%s | market=%s [%s] | account=%s | instruments=%d | positions=%d",
        settings.environment,
        settings.exchange_adapter,
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
    except asyncio.CancelledError:
        pass
    await adapter.close()
    log.info("Sterling shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sterling",
        description="Universal crypto options platform — paper trading, engine-driven",
        version="0.3.0",
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
