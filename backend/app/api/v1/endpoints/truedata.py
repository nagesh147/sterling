"""TrueData Provider API Endpoints — multi-tenant credential management & historical data."""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

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
