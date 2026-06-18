"""Kite triple-SuperTrend engine endpoints — `/api/v1/kite/engine/*`.

Scoped to the calling Kite user. Advisory by default; auto-execute is opt-in via
config and runs through the same Kite order path + live-safety gate as manual
orders. Imports no other engine's strategy/signal/derivative logic.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import UserContext, get_current_user
from app.core.logging import get_logger
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.schemas import (
    ActivityResponse, ContractScanEntry, EngineConfigModel, EngineDetailResponse,
    EngineOrderRequest, EngineOrderResponse, ScanReportResponse, ScanReportSummary,
    SetupChart, SignalsResponse,
)
from app.services import live_safety
from app.services.exchanges.kite import accounts as kite_accounts
from app.services.exchanges.kite.errors import KiteError
from app.services.kite_engine import service, state
from app.services.kite_engine.detail import build_detail
from app.services.kite_engine.scanner import build_setup_chart, scanner

log = get_logger(__name__)
router = APIRouter(prefix="/kite/engine", tags=["kite-engine"])


def _ts_cfg(c: EngineConfigModel) -> TripleSupertrendConfig:
    return TripleSupertrendConfig(trail_target=c.trail_target, early_lock=c.early_lock)


def _client(user: UserContext):
    acct = kite_accounts.get_active(user.user_id)
    if not acct:
        raise HTTPException(409, "No active Kite account — add credentials and log in first.")
    return kite_accounts.build_client(acct)


@router.get("/config", response_model=EngineConfigModel)
async def get_config(user: UserContext = Depends(get_current_user)) -> EngineConfigModel:
    return state.get_config(user.user_id)


@router.post("/config", response_model=EngineConfigModel)
async def set_config(body: EngineConfigModel,
                     user: UserContext = Depends(get_current_user)) -> EngineConfigModel:
    return state.set_config(user.user_id, body)


@router.post("/config/reset", response_model=EngineConfigModel)
async def reset_config(user: UserContext = Depends(get_current_user)) -> EngineConfigModel:
    return state.set_config(user.user_id, EngineConfigModel())


@router.get("/signals", response_model=SignalsResponse)
async def signals(user: UserContext = Depends(get_current_user)) -> SignalsResponse:
    uid = user.user_id
    us = scanner.snapshot(uid)
    st = state.status(uid)
    return SignalsResponse(generated_ms=us.generated_ms, scanning=us.scanning, scanning_label=us.scanning_label, rows=us.rows,
                           next_scan_ms=st.next_scan_ms, auto_scan=service.is_auto_running())


@router.get("/activity", response_model=ActivityResponse)
async def activity(limit: int = 2000,
                   user: UserContext = Depends(get_current_user)) -> ActivityResponse:
    uid = user.user_id
    st = state.status(uid)
    return ActivityResponse(
        events=state.activity(uid, limit), scanning=st.scanning,
        auto_scan=service.is_auto_running(), last_scan_ms=st.last_scan_ms,
        next_scan_ms=st.next_scan_ms, signal_count=st.signal_count,
    )


@router.post("/scan", response_model=SignalsResponse)
async def run_scan(user: UserContext = Depends(get_current_user)) -> SignalsResponse:
    """Manual scan trigger (the background loop also scans automatically)."""
    uid = user.user_id
    client = _client(user)
    try:
        await service.scan_user(client, uid)
    finally:
        await client.close()
    us = scanner.snapshot(uid)
    st = state.status(uid)
    return SignalsResponse(generated_ms=us.generated_ms, scanning=us.scanning, scanning_label=us.scanning_label, rows=us.rows,
                           next_scan_ms=st.next_scan_ms, auto_scan=service.is_auto_running())


@router.post("/scan/cancel", response_model=SignalsResponse)
async def cancel_scan(user: UserContext = Depends(get_current_user)) -> SignalsResponse:
    """Force-stop a running scan. Returns the current snapshot after cancellation."""
    uid = user.user_id
    cancelled = scanner.cancel(uid)
    if cancelled:
        state.log(uid, "info", "Scan cancelled by user.")
        state.set_scanning(uid, False)
        state.set_cooldown(uid)
    us = scanner.snapshot(uid)
    st = state.status(uid)
    return SignalsResponse(generated_ms=us.generated_ms, scanning=us.scanning, scanning_label=us.scanning_label, rows=us.rows,
                           next_scan_ms=st.next_scan_ms, auto_scan=service.is_auto_running())


@router.get("/setup/{token}", response_model=SetupChart)
async def setup(token: int, underlying: str = "",
                user: UserContext = Depends(get_current_user)) -> SetupChart:
    client = _client(user)
    try:
        return await build_setup_chart(client, token, underlying, _ts_cfg(state.get_config(user.user_id)))
    finally:
        await client.close()


@router.post("/order", response_model=EngineOrderResponse)
async def place_order(body: EngineOrderRequest,
                     user: UserContext = Depends(get_current_user)) -> EngineOrderResponse:
    """Place a manual BUY/SELL from the detail panel — same live-safety gate as the
    standard order path, but logged to the engine terminal with full error surfacing."""
    uid = user.user_id
    side = "buy" if body.side.upper() == "BUY" else "sell"
    idem = live_safety.make_idempotency_key(uid, body.option_symbol, body.side.upper(), body.quantity)
    decision = live_safety.assert_safe_to_trade(positions=[], idempotency_key=idem)
    if not decision.allowed and decision.code != "duplicate_order":
        state.log(uid, "order_blocked", f"{body.side} {body.option_symbol} blocked: {decision.reason}")
        raise HTTPException(423, detail={"reason": decision.reason, "code": decision.code})
    prior = live_safety.check_idempotency(idem)
    if prior:
        return EngineOrderResponse(order_id=prior, status="duplicate", message="Already submitted")

    client = _client(user)
    try:
        result = await client.place_order_option(
            body.option_symbol, side, body.quantity, exchange=body.exchange, tag=idem)
    except KiteError as exc:
        state.log(uid, "order_failed", f"{body.side} {body.option_symbol}: {exc}")
        raise HTTPException(502, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        state.log(uid, "order_failed", f"{body.side} {body.option_symbol}: {exc}")
        raise HTTPException(502, detail=str(exc))
    finally:
        await client.close()

    oid = (result or {}).get("order_id", "")
    if oid:
        live_safety.record_idempotency(idem, oid)
    state.log(uid, "order_placed", f"{body.side} {body.quantity} {body.option_symbol} (#{oid})")
    return EngineOrderResponse(order_id=oid, status="ok", message="Order submitted")


@router.get("/detail/{token}", response_model=EngineDetailResponse)
async def detail(token: int, timestamp_ms: int = 0, user: UserContext = Depends(get_current_user)) -> EngineDetailResponse:
    """Trigger context + live underlying price + per-leg quote/depth/greeks for a
    ready signal (BUY/SELL are placed via the standard /kite/orders endpoint)."""
    client = _client(user)
    try:
        d = await build_detail(client, user.user_id, token, timestamp_ms)
    finally:
        await client.close()
    if d is None:
        raise HTTPException(404, "No ready signal for that instrument in the latest scan.")
    return d


@router.get("/scan-report", response_model=ScanReportResponse)
async def scan_report(user: UserContext = Depends(get_current_user)) -> ScanReportResponse:
    """Per-contract scan trace — every option contract evaluated, with bars, premium,
    and reason. Shows exactly which contracts fired and why others didn't."""
    uid = user.user_id
    snap = scanner.snapshot(uid)
    diag = snap.diag
    entries = [
        ContractScanEntry(
            underlying=c.underlying, symbol=c.symbol, strike=c.strike,
            option_type=c.option_type, expiry=c.expiry, moneyness=c.moneyness,
            bars=c.bars, premium_close=c.premium_close, fired=c.fired,
            fired_at_ms=c.fired_at_ms, reason=c.reason,
        )
        for c in diag.contracts
    ]
    total_ce = sum(1 for c in diag.contracts if c.option_type == "CE")
    total_pe = sum(1 for c in diag.contracts if c.option_type == "PE")
    fired_ce = sum(1 for c in diag.contracts if c.option_type == "CE" and c.fired)
    fired_pe = sum(1 for c in diag.contracts if c.option_type == "PE" and c.fired)
    summary = ScanReportSummary(
        generated_ms=snap.generated_ms,
        scan_source="derivatives",  # contracts = derivatives only
        indices=[],  # TODO: pull from config if needed
        total_contracts=len(entries),
        charted=diag.deriv_charts,
        fired=diag.deriv_fired,
        no_data=diag.deriv_no_data,
        min_bars=diag.deriv_min_bars,
        max_bars=diag.deriv_max_bars,
        total_ce=total_ce,
        total_pe=total_pe,
        fired_ce=fired_ce,
        fired_pe=fired_pe,
    )
    return ScanReportResponse(summary=summary, entries=entries)
