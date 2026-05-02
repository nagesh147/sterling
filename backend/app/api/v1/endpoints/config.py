"""
Runtime risk config — adjust sizing params without restart.
Data source switching — hot-swap market data adapter.
"""
import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from app.schemas.risk import RiskParams, ScoringWeights
from app.core.config import settings
from app.services.exchanges import instrument_registry as registry
from app.services import adapter_manager as _adm

router = APIRouter(prefix="/config", tags=["config"])

_risk = RiskParams(
    capital=settings.default_capital,
    max_position_pct=settings.max_position_pct,
    max_contracts=settings.max_contracts,
)


def get_runtime_risk() -> RiskParams:
    return _risk


_scoring_weights = ScoringWeights()


def get_scoring_weights() -> ScoringWeights:
    return _scoring_weights


# ─── Risk config ──────────────────────────────────────────────────────────────

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


# ─── Data source ──────────────────────────────────────────────────────────────

class DataSourceRequest(BaseModel):
    exchange: str
    api_key: str = ""
    api_secret: str = ""


class DataSourceResponse(BaseModel):
    exchange: str
    display_name: str
    reachable: bool
    adapter_stack: str
    timestamp_ms: int


@router.get("/data-source", response_model=DataSourceResponse)
async def get_data_source() -> DataSourceResponse:
    name = _adm.get_data_source()
    ad = _adm.get_adapter()
    reachable = False
    if ad:
        try:
            reachable = await ad.ping()
        except Exception:
            pass
    return DataSourceResponse(
        exchange=name,
        display_name=_adm.SUPPORTED_DATA_SOURCES.get(name, name),
        reachable=reachable,
        adapter_stack=f"CachingAdapter > RetryingAdapter > {name.title().replace('_', '')}Adapter",
        timestamp_ms=int(time.time() * 1000),
    )


@router.post("/data-source", response_model=DataSourceResponse)
async def set_data_source(body: DataSourceRequest, request: Request) -> DataSourceResponse:
    exchange = body.exchange.lower()
    if exchange not in _adm.SUPPORTED_DATA_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported exchange: {exchange!r}. Supported: {list(_adm.SUPPORTED_DATA_SOURCES)}",
        )
    try:
        new_adapter = await _adm.switch(exchange, body.api_key, body.api_secret)
        # Keep app.state.adapter in sync for legacy code that reads it directly
        request.app.state.adapter = new_adapter
        reachable = await new_adapter.ping()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to connect to {exchange}: {exc}")

    return DataSourceResponse(
        exchange=exchange,
        display_name=_adm.SUPPORTED_DATA_SOURCES.get(exchange, exchange),
        reachable=reachable,
        adapter_stack=f"CachingAdapter > RetryingAdapter > {exchange.title().replace('_', '')}Adapter",
        timestamp_ms=int(time.time() * 1000),
    )


@router.post("/data-source/invalidate-cache")
async def invalidate_cache() -> dict:
    """Force-clear the market data cache so the next request fetches live data."""
    ad = _adm.get_adapter()
    if ad and hasattr(ad, "invalidate"):
        ad.invalidate()  # type: ignore[attr-defined]
    return {"cleared": True, "timestamp_ms": int(time.time() * 1000)}


# ─── System info ──────────────────────────────────────────────────────────────

class SystemInfo(BaseModel):
    version: str
    environment: str
    exchange_adapter: str
    active_data_source: str
    data_source_display: str
    paper_trading: bool
    real_public_data: bool
    default_underlying: str
    supported_underlyings: List[str]
    underlyings_with_options: List[str]
    adapter_stack: str
    db_path: str
    supported_data_sources: dict
    timestamp_ms: int


@router.get("/info", response_model=SystemInfo)
async def system_info() -> SystemInfo:
    import os
    instruments = registry.list_instruments()
    ds = _adm.get_data_source()
    return SystemInfo(
        version="0.4.0",
        environment=settings.environment,
        exchange_adapter=settings.exchange_adapter,
        active_data_source=ds,
        data_source_display=_adm.SUPPORTED_DATA_SOURCES.get(ds, ds),
        paper_trading=settings.paper_trading,
        real_public_data=settings.real_public_data,
        default_underlying=settings.default_underlying,
        supported_underlyings=[i.underlying for i in instruments],
        underlyings_with_options=[i.underlying for i in instruments if i.has_options],
        adapter_stack=f"CachingAdapter > RetryingAdapter > {ds.title().replace('_', '')}Adapter",
        db_path=os.environ.get("STERLING_DB_PATH", "sterling_paper.db"),
        supported_data_sources=_adm.SUPPORTED_DATA_SOURCES,
        timestamp_ms=int(time.time() * 1000),
    )


# ─── Scoring weights ──────────────────────────────────────────────────────────

@router.get("/scoring-weights", response_model=ScoringWeights)
async def get_scoring_weights_endpoint() -> ScoringWeights:
    return _scoring_weights


@router.put("/scoring-weights", response_model=ScoringWeights)
async def update_scoring_weights(body: ScoringWeights) -> ScoringWeights:
    global _scoring_weights
    _scoring_weights = body
    return _scoring_weights


@router.post("/scoring-weights/reset", response_model=ScoringWeights)
async def reset_scoring_weights() -> ScoringWeights:
    global _scoring_weights
    _scoring_weights = ScoringWeights()
    return _scoring_weights


# ─── Circuit breaker ─────────────────────────────────────────────────────────

@router.get("/circuit-breaker")
async def get_circuit_breaker(request: Request) -> dict:
    cb = getattr(request.app.state, "circuit_breaker", None)
    if cb is None:
        return {"state": "ok", "halted": False, "size_multiplier": 1.0}
    from app.services.execution.circuit_breaker import CircuitState
    state = "halted" if cb.halted else "ok"
    return {"state": state, "halted": cb.halted, "size_multiplier": cb.size_multiplier}


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(request: Request) -> dict:
    cb = getattr(request.app.state, "circuit_breaker", None)
    if cb is not None:
        cb.reset()
    return {"state": "ok", "halted": False, "size_multiplier": 1.0}


# ─── Eval history cap ─────────────────────────────────────────────────────────

class EvalHistoryCapResponse(BaseModel):
    cap: int


@router.get("/eval-history-cap", response_model=EvalHistoryCapResponse)
async def get_eval_history_cap() -> EvalHistoryCapResponse:
    from app.services import eval_history
    return EvalHistoryCapResponse(cap=eval_history.get_cap())


@router.put("/eval-history-cap", response_model=EvalHistoryCapResponse)
async def set_eval_history_cap(cap: int = 50) -> EvalHistoryCapResponse:
    from app.services import eval_history
    eval_history.set_cap(cap)
    return EvalHistoryCapResponse(cap=eval_history.get_cap())
