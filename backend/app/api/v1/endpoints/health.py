import time
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings

router = APIRouter()

_start_ms = int(time.time() * 1000)


class PositionsSummaryHealth(BaseModel):
    open: int
    partially_closed: int = 0
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


@router.get("/health")
async def health(request: Request) -> HealthResponse:
    now_ms = int(time.time() * 1000)
    from app.core.auth import DEFAULT_USER_ID
    from app.services.exchanges.kite import accounts
    account = accounts.get_active(DEFAULT_USER_ID)
    exchange_ok = bool(account and account.connected)

    return HealthResponse(
        status="ok",
        version="0.4.0",
        environment=settings.environment,
        paper_trading=settings.paper_trading,
        real_public_data=settings.real_public_data,
        default_underlying=settings.default_underlying,
        exchange_adapter="zerodha",
        exchange_reachable=exchange_ok,
        positions=PositionsSummaryHealth(open=0, closed=0),
        alerts=AlertsSummaryHealth(active=0, triggered=0),
        cache_keys=None,
        uptime_seconds=int((now_ms - _start_ms) / 1000),
        background_checker="running",
        timestamp_ms=now_ms,
    )
