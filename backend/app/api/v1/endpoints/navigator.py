"""Sterling Value-Flow Navigator endpoints — `/api/v1/kite/navigator/*`.

Kite-only, off-by-default, advisory-first. Follows the exact
`UserContext`/`get_current_user` auth pattern used by
`/api/v1/kite/engine/*` (see `kite_engine.py`) — scoped to the calling
user, no cross-user access.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from app.core.auth import UserContext, get_current_user
from app.core.logging import get_logger
from app.engines.navigator.schemas import NavigatorConfigModel, NavigatorConfigRecord
from app.services.kite_engine import state as kite_engine_state
from app.services.navigator import config_store, repository, service as nav_service
from app.services.navigator.repository import NavigatorStorageError, RevisionConflict

log = get_logger(__name__)
router = APIRouter(prefix="/kite/navigator", tags=["kite-navigator"])

_SERVER_CAPABILITIES = {
    "engine_sources": ["kite_triple_supertrend"],
    "price_timeframe": "60minute",
    "schema_version": 1,
}


def _default_underlyings(uid: str) -> list[str]:
    """Navigator's first-enable default mirrors whatever the user's
    existing Kite engine already scans — no surprise universe expansion."""
    try:
        return list(kite_engine_state.get_config(uid).scan_indices)
    except Exception:
        return []


class ConfigUpdateRequest(BaseModel):
    config: dict
    expected_revision: int


class ConfigResponse(BaseModel):
    record: NavigatorConfigRecord
    capabilities: dict


def _to_response(record: NavigatorConfigRecord) -> ConfigResponse:
    return ConfigResponse(record=record, capabilities=_SERVER_CAPABILITIES)


@router.get("/config")
async def get_config(user: UserContext = Depends(get_current_user)) -> ConfigResponse:
    record = config_store.get(user.user_id, default_underlyings=_default_underlyings(user.user_id))
    return _to_response(record)


@router.put("/config")
async def put_config(body: ConfigUpdateRequest, user: UserContext = Depends(get_current_user)) -> ConfigResponse:
    try:
        new_config = NavigatorConfigModel.model_validate(body.config)
    except ValidationError as exc:
        raise HTTPException(400, f"INVALID_CONFIG: {exc}") from exc

    if new_config.operating_mode == "gate":
        current = config_store.get(user.user_id, default_underlyings=_default_underlyings(user.user_id))
        if current.calibration_readiness != "ready":
            raise HTTPException(423, "GATE_NOT_CALIBRATED: Navigator gate mode requires a promoted calibration report")

    try:
        record = config_store.save(
            user.user_id, new_config, expected_revision=body.expected_revision,
            default_underlyings=_default_underlyings(user.user_id),
        )
    except RevisionConflict as exc:
        raise HTTPException(409, f"REVISION_CONFLICT: {exc}") from exc
    except NavigatorStorageError as exc:
        raise HTTPException(502, f"NAVIGATOR_STORAGE_ERROR: {exc}") from exc
    return _to_response(record)


@router.post("/config/validate")
async def validate_config(body: dict, user: UserContext = Depends(get_current_user)) -> dict:
    try:
        config_store.validate(body)
    except ValidationError as exc:
        raise HTTPException(400, f"INVALID_CONFIG: {exc}") from exc
    return {"valid": True}


@router.post("/config/reset")
async def reset_config(user: UserContext = Depends(get_current_user)) -> ConfigResponse:
    try:
        record = config_store.reset(user.user_id, default_underlyings=_default_underlyings(user.user_id))
    except NavigatorStorageError as exc:
        raise HTTPException(502, f"NAVIGATOR_STORAGE_ERROR: {exc}") from exc
    return _to_response(record)


@router.get("/status")
async def get_status(user: UserContext = Depends(get_current_user)) -> dict:
    status = nav_service.get_status(user.user_id, default_underlyings=_default_underlyings(user.user_id))
    return {
        "health": status.health,
        "enabled": status.enabled,
        "operating_mode": status.operating_mode,
        "calibration_readiness": status.calibration_readiness,
        "config_revision": status.config_revision,
        "activation_watermark_ms": status.activation_watermark_ms,
        "components": [
            {"name": c.name, "quality": c.quality, "last_updated_ms": c.last_updated_ms, "reason_codes": c.reason_codes}
            for c in status.components
        ],
        "last_decision_at_ms": status.last_decision_at_ms,
        "sampler_running": status.sampler_running,
    }


@router.get("/snapshot/{underlying}")
async def get_snapshot(underlying: str, user: UserContext = Depends(get_current_user)) -> dict:
    record = config_store.get(user.user_id, default_underlyings=_default_underlyings(user.user_id))
    if not record.config.enabled:
        raise HTTPException(503, "NAVIGATOR_WARMING_UP: Navigator is disabled for this user")
    matches = nav_service.get_cached_decisions_for_underlying(user.user_id, underlying)
    if not matches:
        raise HTTPException(503, f"NAVIGATOR_WARMING_UP: no evidence cached yet for {underlying}")
    latest = max(matches, key=lambda d: d.generated_at_ms)
    return latest.model_dump(mode="json")


@router.get("/series/{underlying}")
async def get_series(
    underlying: str, since_bar_close_ms: int = 0, limit: int = 500,
    user: UserContext = Depends(get_current_user),
) -> dict:
    limit = max(1, min(limit, 2000))
    rows = nav_service.get_feature_series(user.user_id, underlying, since_bar_close_ms=since_bar_close_ms, limit=limit)
    return {"underlying": underlying, "points": rows}


@router.get("/signals")
async def list_signals(
    underlying: Optional[str] = None, before_generated_at_ms: Optional[int] = None,
    before_decision_id: Optional[str] = None, limit: int = 50,
    user: UserContext = Depends(get_current_user),
) -> dict:
    limit = max(1, min(limit, 200))
    try:
        rows = repository.fetch_signal_events_page(
            user.user_id, underlying=underlying, before_generated_at_ms=before_generated_at_ms,
            before_decision_id=before_decision_id, limit=limit,
        )
    except NavigatorStorageError as exc:
        raise HTTPException(502, f"NAVIGATOR_STORAGE_ERROR: {exc}") from exc
    # Tie-safe cursor: a whole scan's decisions can share one
    # generated_at_ms, so the cursor must carry decision_id too or a page
    # boundary inside that tied group would skip the rest of it forever.
    next_cursor = (
        {"generated_at_ms": rows[-1]["generated_at_ms"], "decision_id": rows[-1]["decision_id"]}
        if len(rows) == limit else None
    )
    return {"decisions": [r["payload_json"] for r in rows], "next_cursor": next_cursor}


@router.get("/signals/{decision_id}")
async def get_signal(decision_id: str, user: UserContext = Depends(get_current_user)) -> dict:
    try:
        row = repository.fetch_signal_event(decision_id)
    except NavigatorStorageError as exc:
        raise HTTPException(502, f"NAVIGATOR_STORAGE_ERROR: {exc}") from exc
    if row is None or row["user_id"] != user.user_id:
        raise HTTPException(404, "signal decision not found")
    import json as _json
    return _json.loads(row["payload_json"])


@router.get("/calibration")
async def get_calibration(user: UserContext = Depends(get_current_user)) -> dict:
    try:
        latest = repository.fetch_latest_calibration_state(user.user_id)
    except NavigatorStorageError as exc:
        raise HTTPException(502, f"NAVIGATOR_STORAGE_ERROR: {exc}") from exc
    record = config_store.get(user.user_id, default_underlyings=_default_underlyings(user.user_id))
    return {
        "calibration_readiness": record.calibration_readiness,
        "calibration_report_id": record.calibration_report_id,
        "latest_report": latest,
    }
