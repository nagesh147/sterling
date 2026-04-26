"""
Alert management.
POST /alerts              — create alert
GET  /alerts              — list all (optionally ?underlying=BTC)
GET  /alerts/triggered    — list triggered only
POST /alerts/check        — check all active alerts against current snapshot
POST /alerts/{id}/dismiss — dismiss (stop showing)
DELETE /alerts/{id}       — delete
"""
import asyncio
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query

from app.schemas.alerts import (
    Alert, AlertCreate, AlertListResponse, AlertsCheckResponse,
    AlertCheckResult, AlertStatus,
)
from app.services import alert_store
from app.services import webhook_store
from app.services.exchanges import instrument_registry as registry
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup
from app.engines.directional.orchestrator import compute_ivr

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(underlying: str = Query(default="")) -> AlertListResponse:
    alerts = alert_store.list_alerts(underlying=underlying.strip() or None)
    return AlertListResponse(
        alerts=alerts,
        active_count=alert_store.active_count(),
        triggered_count=alert_store.triggered_count(),
    )


@router.get("/triggered", response_model=AlertListResponse)
async def list_triggered() -> AlertListResponse:
    all_alerts = alert_store.list_alerts()
    triggered = [a for a in all_alerts if a.status == AlertStatus.TRIGGERED]
    return AlertListResponse(
        alerts=triggered,
        active_count=alert_store.active_count(),
        triggered_count=len(triggered),
    )


@router.post("", response_model=Alert)
async def create_alert(body: AlertCreate) -> Alert:
    sym = body.underlying.upper()
    if not registry.is_supported(sym):
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")
    return alert_store.add_alert(body)


@router.post("/check", response_model=AlertsCheckResponse)
async def check_alerts(request: Request) -> AlertsCheckResponse:
    """
    Check all ACTIVE alerts against current market data.
    Fires (marks triggered) any alert whose condition is met.
    """
    now_ms = int(time.time() * 1000)

    # Rearm any triggered alerts whose cooldown has elapsed before checking
    for a in alert_store.list_alerts():
        if a.status == AlertStatus.TRIGGERED:
            alert_store.rearm_if_cooldown_elapsed(a.id)

    active_alerts = [a for a in alert_store.list_alerts() if a.status == AlertStatus.ACTIVE]
    from app.services import adapter_manager as _adm
    adapter = _adm.get_adapter() or request.app.state.adapter
    results: list[AlertCheckResult] = []
    newly_triggered = 0

    # Group by underlying for efficiency
    underlyings = list({a.underlying for a in active_alerts})
    snapshots: dict = {}

    for sym in underlyings:
        inst = registry.get_instrument(sym)
        if not inst:
            continue
        try:
            spot = await adapter.get_index_price(inst)
            c4h = await adapter.get_candles(inst, "4H", limit=100)
            c1h = await adapter.get_candles(inst, "1H", limit=200)
            regime = compute_regime(c4h)
            signal = compute_signal(c1h)
            setup = evaluate_setup(regime, signal)
            ivr = await compute_ivr(adapter, inst, c1h)
            snapshots[sym] = {
                "spot": spot,
                "ivr": ivr,
                "green_arrow": signal.green_arrow,
                "red_arrow": signal.red_arrow,
                "state": setup.state.value,
            }
        except Exception:
            snapshots[sym] = {}

    for alert in active_alerts:
        snap = snapshots.get(alert.underlying, {})
        result = alert_store.check_alert(
            alert,
            spot_price=snap.get("spot"),
            ivr=snap.get("ivr"),
            green_arrow=snap.get("green_arrow", False),
            red_arrow=snap.get("red_arrow", False),
            current_state=snap.get("state"),
        )
        results.append(result)
        if result.triggered:
            alert_store.fire_alert(alert.id, trigger_value=result.current_value)
            newly_triggered += 1
            # Fire webhooks asynchronously — don't block response
            subject = f"{alert.underlying} Alert: {alert.condition.value}"
            asyncio.create_task(
                webhook_store.deliver_all(subject, result.message, {
                    "underlying": alert.underlying,
                    "condition": alert.condition.value,
                    "threshold": alert.threshold,
                    "value": result.current_value,
                })
            )

    return AlertsCheckResponse(
        checked=len(active_alerts),
        newly_triggered=newly_triggered,
        results=results,
        timestamp_ms=now_ms,
    )


@router.post("/{alert_id}/dismiss", response_model=Alert)
async def dismiss_alert(alert_id: str) -> Alert:
    alert = alert_store.dismiss_alert(alert_id.upper())
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert


@router.get("/{alert_id}", response_model=Alert)
async def get_alert(alert_id: str) -> Alert:
    alert = alert_store.get_alert(alert_id.upper())
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert


@router.put("/{alert_id}", response_model=Alert)
async def update_alert(alert_id: str, body: AlertCreate) -> Alert:
    existing = alert_store.get_alert(alert_id.upper())
    if not existing:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    updated = alert_store._alerts[alert_id.upper()].model_copy(update={
        "threshold": body.threshold,
        "cooldown_hours": body.cooldown_hours,
        "notes": body.notes,
        "target_state": body.target_state,
    })
    alert_store._alerts[alert_id.upper()] = updated
    return updated


@router.delete("", status_code=204)
async def bulk_clear_dismissed() -> None:
    """Delete all dismissed alerts."""
    dismissed_ids = [a.id for a in alert_store.list_alerts() if a.status == AlertStatus.DISMISSED]
    for aid in dismissed_ids:
        alert_store.delete_alert(aid)


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: str) -> None:
    if not alert_store.delete_alert(alert_id.upper()):
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
