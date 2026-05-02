import dataclasses
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.core.trading_mode import MODES, DEFAULT_MODE, TradingModeConfig

router = APIRouter(prefix="/config", tags=["config"])


def _mode_to_dict(cfg: TradingModeConfig) -> dict:
    d = dataclasses.asdict(cfg)
    d["dte_preferred"] = list(cfg.dte_preferred)
    d["trail_mode"] = cfg.trail_mode.value
    return d


class TradingModeRequest(BaseModel):
    name: str


@router.get("/trading-mode")
async def get_trading_mode(request: Request) -> dict:
    mode = getattr(request.app.state, "trading_mode", MODES[DEFAULT_MODE])
    return {"name": mode.name, "config": _mode_to_dict(mode)}


@router.put("/trading-mode")
async def set_trading_mode(body: TradingModeRequest, request: Request) -> dict:
    if body.name not in MODES:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {body.name!r}. Valid: {list(MODES)}")
    from app.services.db import set_trading_mode as _db_set
    _db_set(body.name)
    request.app.state.trading_mode = MODES[body.name]
    mode = MODES[body.name]
    return {"name": mode.name, "config": _mode_to_dict(mode)}


@router.get("/trading-mode/all")
async def get_all_trading_modes() -> dict:
    return {name: _mode_to_dict(cfg) for name, cfg in MODES.items()}
