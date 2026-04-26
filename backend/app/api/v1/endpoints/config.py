"""
Runtime risk config — adjust sizing params without restart.
Single-process in-memory; survives only until process exit.
"""
import time
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.schemas.risk import RiskParams
from app.core.config import settings
from app.services.exchanges import instrument_registry as registry

router = APIRouter(prefix="/config", tags=["config"])

_risk = RiskParams(
    capital=settings.default_capital,
    max_position_pct=settings.max_position_pct,
    max_contracts=settings.max_contracts,
)


def get_runtime_risk() -> RiskParams:
    return _risk


class SystemInfo(BaseModel):
    version: str
    environment: str
    exchange_adapter: str
    paper_trading: bool
    real_public_data: bool
    default_underlying: str
    supported_underlyings: List[str]
    underlyings_with_options: List[str]
    adapter_stack: str
    db_path: str
    timestamp_ms: int


@router.get("/risk", response_model=RiskParams)
async def get_risk_config() -> RiskParams:
    return _risk


@router.put("/risk", response_model=RiskParams)
async def update_risk_config(params: RiskParams) -> RiskParams:
    global _risk
    _risk = params
    return _risk


@router.post("/risk/reset", response_model=RiskParams)
async def reset_risk_config() -> RiskParams:
    global _risk
    _risk = RiskParams(
        capital=settings.default_capital,
        max_position_pct=settings.max_position_pct,
        max_contracts=settings.max_contracts,
    )
    return _risk


@router.get("/info", response_model=SystemInfo)
async def system_info() -> SystemInfo:
    import os
    instruments = registry.list_instruments()
    return SystemInfo(
        version="0.3.0",
        environment=settings.environment,
        exchange_adapter=settings.exchange_adapter,
        paper_trading=settings.paper_trading,
        real_public_data=settings.real_public_data,
        default_underlying=settings.default_underlying,
        supported_underlyings=[i.underlying for i in instruments],
        underlyings_with_options=[i.underlying for i in instruments if i.has_options],
        adapter_stack="CachingAdapter > RetryingAdapter > "
                      + ("DeribitAdapter" if settings.exchange_adapter == "deribit" else "OKXAdapter"),
        db_path=os.environ.get("STERLING_DB_PATH", "sterling_paper.db"),
        timestamp_ms=int(time.time() * 1000),
    )
