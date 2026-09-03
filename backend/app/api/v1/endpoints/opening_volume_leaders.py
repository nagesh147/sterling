"""Advisory API for the opening-volume leader signal engine."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import UserContext, get_current_user
from app.engines.nifty_orb_options import Bar
from app.engines.opening_volume_leaders import (
    STRATEGY_CONTRACT,
    OpeningVolumeConfig,
    evaluate_leader,
)
from app.services.opening_volume_leaders import LiveLeaderScanConfig

router = APIRouter(prefix="/opening-volume-leaders", tags=["opening-volume-leaders"])


class OpeningVolumeBarRequest(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class OpeningVolumeEvaluateRequest(BaseModel):
    symbol: str
    as_of: datetime
    bars: list[OpeningVolumeBarRequest] = Field(min_length=1, max_length=25_000)
    average_turnover_inr: float | None = None
    config: dict = Field(default_factory=dict)


class OpeningVolumeLiveScanRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    scan_all_stocks: bool = True
    include_watch: bool = False
    max_candidates: int = 40
    concurrency: int = 3
    history_calendar_days: int = 45
    config: dict = Field(default_factory=dict)


@router.get("/contract")
async def contract() -> dict:
    return {
        "strategy": STRATEGY_CONTRACT,
        "defaults": OpeningVolumeConfig().__dict__,
        "tier_score": "not implemented: source weights are not observable",
    }


@router.post("/evaluate")
async def evaluate(body: OpeningVolumeEvaluateRequest) -> dict:
    """Deterministically evaluate supplied one-minute OHLCV without broker I/O."""

    try:
        config = OpeningVolumeConfig(**body.config).validate()
        bars = [
            Bar(
                timestamp=row.timestamp,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in body.bars
        ]
        return {
            "strategy": STRATEGY_CONTRACT,
            "signal": evaluate_leader(
                body.symbol,
                bars,
                as_of=body.as_of,
                config=config,
                average_turnover_inr=body.average_turnover_inr,
            ).to_dict(),
        }
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/scan")
async def scan(
    body: OpeningVolumeLiveScanRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict:
    """Scan the authenticated user's Kite universe; never submit an order."""

    try:
        scan_config = LiveLeaderScanConfig(
            symbols=tuple(body.symbols),
            scan_all_stocks=body.scan_all_stocks,
            include_watch=body.include_watch,
            max_candidates=body.max_candidates,
            concurrency=body.concurrency,
            history_calendar_days=body.history_calendar_days,
        ).validate()
        signal_config = OpeningVolumeConfig(**body.config).validate()
        from app.services.opening_volume_leaders import scan_kite_leaders

        return await scan_kite_leaders(
            str(user.user_id),
            scan_config=scan_config,
            signal_config=signal_config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
