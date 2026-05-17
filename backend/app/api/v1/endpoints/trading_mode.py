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

    # ── Mode-change cache invalidation ────────────────────────────────────
    # The snapshot cache stores SL/TP and signal payloads computed under the
    # *previous* mode's stop_atr_mult / rr_target. The signal-id cache stores
    # mode-coded IDs (e.g. BTCFUT-SC-XXX). Without eviction here the SSE
    # serves stale data for up to 45 s + 30 s before the background refresher
    # overwrites it — long enough for users to see e.g. INTRADAY signals
    # rendered as scalping (BTCFUT-SC-...).
    try:
        from app.services import snapshot_cache as _snap_cache
        _snap_cache.clear()
    except Exception:
        pass
    try:
        # Drop in-memory signal-id cache. Keeping it would cause the next
        # SSE tick to serve old-mode IDs because the (sym, mode, dir) key
        # for the new mode is empty, but the OLD-mode entry persists and
        # could be matched if a downstream consumer looked it up under the
        # legacy 2-part key during a partial migration.
        from app.api.v1.endpoints.directional import (
            _active_signal_ids, _save_signal_tracker_state,
        )
        _active_signal_ids.clear()
        try:
            _save_signal_tracker_state()
        except Exception:
            pass
    except Exception:
        pass

    return {"name": mode.name, "config": _mode_to_dict(mode)}


@router.get("/trading-mode/all")
async def get_all_trading_modes() -> dict:
    return {name: _mode_to_dict(cfg) for name, cfg in MODES.items()}
