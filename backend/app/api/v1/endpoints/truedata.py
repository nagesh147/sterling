"""TrueData Provider API Endpoints — multi-tenant credential management & historical data."""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.auth import UserContext, get_current_user
from app.core.logging import get_logger
from app.services.providers import truedata as truedata_service

log = get_logger(__name__)
router = APIRouter(prefix="/truedata", tags=["truedata"])


def _require_active(user: UserContext):
    acct = truedata_service.get_active(user.user_id)
    if not acct:
        raise HTTPException(409, "No active TrueData credentials configured.")
    return acct


# ── Credential Management Routes ──────────────────────────────────────────────
@router.get("/credentials")
async def list_credentials(user: UserContext = Depends(get_current_user)) -> List[truedata_service.TrueDataCredentialResponse]:
    accts = truedata_service.list_credentials(user.user_id)
    return [truedata_service.to_response(a) for a in accts]


@router.post("/credentials")
async def add_credentials(
    body: truedata_service.TrueDataCredentialCreate,
    user: UserContext = Depends(get_current_user),
) -> truedata_service.TrueDataCredentialResponse:
    a = truedata_service.add(user.user_id, body)
    return truedata_service.to_response(a)


@router.put("/credentials/{account_id}")
async def update_credentials(
    account_id: str,
    body: truedata_service.TrueDataCredentialUpdate,
    user: UserContext = Depends(get_current_user),
) -> truedata_service.TrueDataCredentialResponse:
    a = truedata_service.update(user.user_id, account_id, body)
    if not a:
        raise HTTPException(404, "TrueData credential not found")
    return truedata_service.to_response(a)


@router.delete("/credentials/{account_id}", status_code=204)
async def delete_credentials(account_id: str, user: UserContext = Depends(get_current_user)) -> None:
    if not truedata_service.delete(user.user_id, account_id):
        raise HTTPException(404, "TrueData credential not found")


class TrueDataSettingsModel(BaseModel):
    data_source: str = "truedata"  # "truedata" | "zerodhakite"


@router.get("/settings")
async def get_settings(user: UserContext = Depends(get_current_user)) -> TrueDataSettingsModel:
    from app.services.db import get_config
    src = get_config("market_data_source") or "truedata"
    if src not in ("truedata", "zerodhakite"):
        src = "truedata"
    return TrueDataSettingsModel(data_source=src)


@router.post("/settings")
async def update_settings(
    body: TrueDataSettingsModel,
    user: UserContext = Depends(get_current_user),
) -> TrueDataSettingsModel:
    from app.services.db import set_config
    src = body.data_source if body.data_source in ("truedata", "zerodhakite") else "truedata"
    set_config("market_data_source", src)
    return TrueDataSettingsModel(data_source=src)


@router.get("/status")
async def get_status(user: UserContext = Depends(get_current_user)) -> truedata_service.TrueDataStatus:
    acct = truedata_service.get_active(user.user_id)
    if not acct:
        return truedata_service.TrueDataStatus(
            connected=False,
            is_active=False,
            message="No active TrueData credentials",
        )
    return truedata_service.TrueDataStatus(
        connected=acct.connected,
        is_active=acct.is_active,
        account_id=acct.id,
        username_hint=acct.username_hint(),
        message="Credentials configured",
    )


# ── Market Data History Routes (via Adapter) ──────────────────────────────────
@router.get("/bars")
async def get_bars(
    symbol: str = Query(...),
    start: str = Query(..., alias="from"),
    end: str = Query(..., alias="to"),
    interval: str = Query("1min"),
    user: UserContext = Depends(get_current_user),
):
    """Fetch historical bars and return as list of CanonicalMarketEvents."""
    acct = _require_active(user)
    client = truedata_service.build_client(acct)
    try:
        raw_bars = await client.get_bars(symbol, start, end, interval=interval)
        events = [
            truedata_service.TrueDataMarketDataAdapter.create_bar_event(symbol, b).payload
            for b in raw_bars
        ]
        return {"symbol": symbol, "interval": interval, "count": len(events), "events": events}
    except truedata_service.TrueDataError as exc:
        raise HTTPException(502, str(exc)) from exc
    finally:
        await client.aclose()


@router.get("/ticks")
async def get_ticks(
    symbol: str = Query(...),
    start: str = Query(..., alias="from"),
    end: str = Query(..., alias="to"),
    bidask: int = Query(1, ge=0, le=1),
    user: UserContext = Depends(get_current_user),
):
    """Fetch historical ticks and return as list of CanonicalMarketEvents."""
    acct = _require_active(user)
    client = truedata_service.build_client(acct)
    try:
        raw_ticks = await client.get_ticks(symbol, start, end, bidask=bidask)
        events = [
            truedata_service.TrueDataMarketDataAdapter.create_tick_event(symbol, t, sequence=idx).payload
            for idx, t in enumerate(raw_ticks)
        ]
        return {"symbol": symbol, "count": len(events), "events": events}
    except truedata_service.TrueDataError as exc:
        raise HTTPException(502, str(exc)) from exc
    finally:
        await client.aclose()


@router.get("/structure")
async def get_structure(
    symbol: str = Query(...),
    start: str = Query(..., alias="from"),
    end: str = Query(..., alias="to"),
    tick_size: float = Query(1.0, gt=0),
    user: UserContext = Depends(get_current_user),
):
    """Calculate causal market profile, volume profile, VWAP, and CVD structure for any symbol."""
    from app.engines.adaptive_edge.structure import build_structure_series

    acct = _require_active(user)
    client = truedata_service.build_client(acct)
    try:
        raw_bars = await client.get_bars(symbol, start, end, interval="1min")
        bar_events = [
            truedata_service.TrueDataMarketDataAdapter.create_bar_event(symbol, b, sequence=idx)
            for idx, b in enumerate(raw_bars)
        ]
        try:
            raw_ticks = await client.get_ticks(symbol, start, end, bidask=1)
        except truedata_service.TrueDataNoDataError:
            raw_ticks = []
        tick_events = [
            truedata_service.TrueDataMarketDataAdapter.create_tick_event(symbol, t, sequence=idx)
            for idx, t in enumerate(raw_ticks)
        ]
        series = build_structure_series(bar_events, tick_events, tick_size=tick_size)
        snapshots = [
            {
                "close": s.close,
                "vwap": s.vwap,
                "poc": s.poc,
                "vah": s.vah,
                "val": s.val,
                "vpoc": s.vpoc,
                "vp_vah": s.vp_vah,
                "vp_val": s.vp_val,
                "cvd": s.cvd,
                "bar_delta": s.bar_delta,
                "buy_volume": s.buy_volume,
                "sell_volume": s.sell_volume,
                "spread": s.spread,
                "location": s.location,
                "flow_sign": s.flow_sign,
                "session_open": s.session_open,
                "ib_high": s.ib_high,
                "ib_low": s.ib_low,
                "ib_complete": s.ib_complete,
                "or_location": s.or_location,
                "vwap_location": s.vwap_location,
                "poc_migration": s.poc_migration,
                "hvn": list(s.hvn),
                "lvn": list(s.lvn),
                "nearest_hvn": s.nearest_hvn,
                "nearest_lvn": s.nearest_lvn,
            }
            for s in series
        ]
        return {
            "symbol": symbol,
            "bar_count": len(bar_events),
            "tick_count": len(tick_events),
            "structure": snapshots[-1] if snapshots else None,
            "snapshots_count": len(snapshots),
        }
    except truedata_service.TrueDataError as exc:
        raise HTTPException(502, str(exc)) from exc
    finally:
        await client.aclose()

