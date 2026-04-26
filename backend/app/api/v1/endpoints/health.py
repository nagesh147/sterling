import time
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings
from app.services import paper_store

router = APIRouter()


class PositionsSummaryHealth(BaseModel):
    open: int
    closed: int


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
    cache_keys: Optional[int] = None
    timestamp_ms: int


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    now_ms = int(time.time() * 1000)

    adapter = getattr(request.app.state, "adapter", None)
    exchange_ok = None
    cache_keys = None

    if adapter:
        try:
            exchange_ok = await adapter.ping()
        except Exception:
            exchange_ok = False

        # CachingAdapter exposes _cache
        inner = adapter
        if hasattr(inner, "_cache"):
            cache_keys = len(inner._cache)

    return HealthResponse(
        status="ok",
        version="0.3.0",
        environment=settings.environment,
        paper_trading=settings.paper_trading,
        real_public_data=settings.real_public_data,
        default_underlying=settings.default_underlying,
        exchange_adapter=settings.exchange_adapter,
        exchange_reachable=exchange_ok,
        positions=PositionsSummaryHealth(
            open=paper_store.open_count(),
            closed=paper_store.closed_count(),
        ),
        cache_keys=cache_keys,
        timestamp_ms=now_ms,
    )
