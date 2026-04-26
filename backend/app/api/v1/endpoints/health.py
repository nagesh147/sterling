import time
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings
from app.services import paper_store, alert_store

router = APIRouter()

_start_ms = int(time.time() * 1000)


class PositionsSummaryHealth(BaseModel):
    open: int
    closed: int


class AlertsSummaryHealth(BaseModel):
    active: int
    triggered: int


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    paper_trading: bool
    real_public_data: bool
    default_underlying: str
    exchange_adapter: str
    exchange_reachable: Optional[bool] = None
    positions: PositionsSummaryHealth
    alerts: AlertsSummaryHealth
    cache_keys: Optional[int] = None
    uptime_seconds: int
    background_checker: str  # "running" | "disabled"
    timestamp_ms: int


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    now_ms = int(time.time() * 1000)
    from app.services import adapter_manager as _adm
    adapter = _adm.get_adapter() or getattr(request.app.state, "adapter", None)
    exchange_ok = None
    cache_keys = None

    if adapter:
        try:
            exchange_ok = await adapter.ping()
        except Exception:
            exchange_ok = False
        if hasattr(adapter, "_cache"):
            cache_keys = len(adapter._cache)

    return HealthResponse(
        status="ok",
        version="0.4.0",
        environment=settings.environment,
        paper_trading=settings.paper_trading,
        real_public_data=settings.real_public_data,
        default_underlying=settings.default_underlying,
        exchange_adapter=_adm.get_data_source(),
        exchange_reachable=exchange_ok,
        positions=PositionsSummaryHealth(
            open=paper_store.open_count(),
            closed=paper_store.closed_count(),
        ),
        alerts=AlertsSummaryHealth(
            active=alert_store.active_count(),
            triggered=alert_store.triggered_count(),
        ),
        cache_keys=cache_keys,
        uptime_seconds=int((now_ms - _start_ms) / 1000),
        background_checker="running",
        timestamp_ms=now_ms,
    )
