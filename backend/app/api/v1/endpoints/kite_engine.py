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
    ActivityResponse, BacktestRequest, BacktestResponse, ContractScanEntry,
    EngineConfigModel, EngineDetailResponse, EngineOrderRequest, EngineOrderResponse,
    OpenPositionRecord, OpenPositionsResponse,
    ScanReportResponse, ScanReportSummary, SetupChart, SignalsResponse,
)
from app.services import live_safety
from app.services.exchanges.kite import accounts as kite_accounts
from app.services.exchanges.kite.errors import KiteError
from app.services.kite_engine import positions as kite_positions, service, state
from app.services.kite_engine.detail import build_detail
from app.services.kite_engine.market_hours import is_market_open
from app.services.kite_engine.scanner import build_setup_chart, scanner

log = get_logger(__name__)
router = APIRouter(prefix="/kite/engine", tags=["kite-engine"])


def _ts_cfg(c: EngineConfigModel) -> TripleSupertrendConfig:
    return TripleSupertrendConfig(trail_target=c.trail_target, early_lock=c.early_lock)


async def _client(user: UserContext):
    acct = kite_accounts.get_active(user.user_id)
    if not acct:
        raise HTTPException(409, "No active Kite account — add credentials and log in first.")
    return await kite_accounts.acquire_client(acct)   # warm, cached (no per-call close)


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


@router.post("/backtest", response_model=BacktestResponse)
async def backtest(body: BacktestRequest,
                   user: UserContext = Depends(get_current_user)) -> BacktestResponse:
    """Honest options backtest (workstream H). data_mode synthetic | real | both:
    synthetic replays the signal on real underlying history with BS-modeled premium
    (full history, modeled price); real replays an actual live-contract premium
    series (true price, short lookback); both runs each + reports BS-vs-real drift.
    Read-only: no orders, no live-safety gate."""
    from app.services.kite_engine import backtest_service
    client = await _client(user)
    try:
        result = await backtest_service.run_backtest(client, body)
    except KiteError as exc:
        raise HTTPException(502, f"Kite data fetch failed: {exc}")
    return BacktestResponse(**result)


@router.get("/signals", response_model=SignalsResponse)
async def signals(user: UserContext = Depends(get_current_user)) -> SignalsResponse:
    uid = user.user_id
    us = scanner.snapshot(uid)
    st = state.status(uid)
    return SignalsResponse(generated_ms=us.generated_ms, scanning=us.scanning, scanning_label=us.scanning_label, rows=us.rows,
                           next_scan_ms=st.next_scan_ms, auto_scan=service.is_auto_running(),
                           market_open=is_market_open())


@router.get("/activity", response_model=ActivityResponse)
async def activity(limit: int = 2000,
                   user: UserContext = Depends(get_current_user)) -> ActivityResponse:
    uid = user.user_id
    st = state.status(uid)
    us = scanner.snapshot(uid)
    return ActivityResponse(
        events=state.activity(uid, limit), scanning=st.scanning, auto_scan=service.is_auto_running(),
        last_scan_ms=st.last_scan_ms, next_scan_ms=st.next_scan_ms, signal_count=st.signal_count,
        scanning_label=us.scanning_label if us.scanning else "",
    )


@router.get("/server-logs")
async def server_logs(limit: int = 300,
                      user: UserContext = Depends(get_current_user)) -> dict:
    """Recent backend server logs (in-memory ring buffer) for the Kite Terminal.
    Lets the UI interleave real server logs with engine activity. Read-only."""
    from app.core.logging import recent_logs
    return {"logs": recent_logs(limit)}


@router.post("/scan", response_model=SignalsResponse)
async def run_scan(user: UserContext = Depends(get_current_user)) -> SignalsResponse:
    """Manual scan trigger (the background loop also scans automatically)."""
    uid = user.user_id
    client = await _client(user)
    await service.scan_user(client, uid)
    us = scanner.snapshot(uid)
    st = state.status(uid)
    return SignalsResponse(generated_ms=us.generated_ms, scanning=us.scanning, scanning_label=us.scanning_label, rows=us.rows,
                           next_scan_ms=st.next_scan_ms, auto_scan=service.is_auto_running(),
                           market_open=is_market_open())


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
                           next_scan_ms=st.next_scan_ms, auto_scan=service.is_auto_running(),
                           market_open=is_market_open())


@router.get("/setup/{token}", response_model=SetupChart)
async def setup(token: int, underlying: str = "",
                user: UserContext = Depends(get_current_user)) -> SetupChart:
    client = await _client(user)
    return await build_setup_chart(client, token, underlying, _ts_cfg(state.get_config(user.user_id)))


@router.post("/order", response_model=EngineOrderResponse)
async def place_order(body: EngineOrderRequest,
                     user: UserContext = Depends(get_current_user)) -> EngineOrderResponse:
    """Place a manual BUY/SELL from the detail panel — same live-safety gate as the
    standard order path, but logged to the engine terminal with full error surfacing."""
    res = await service.place_manual_order(
        user.user_id, body.option_symbol, body.side, body.quantity, body.exchange)
    if res["status"] == "blocked":
        raise HTTPException(423, detail={"reason": res.get("reason"), "code": res.get("code")})
    if res["status"] == "error":
        raise HTTPException(502, detail=res.get("message", "Order failed"))
    return EngineOrderResponse(
        order_id=res.get("order_id", ""), status=res["status"],
        message=res.get("message", ""))


@router.get("/detail/{token}", response_model=EngineDetailResponse)
async def detail(token: int, timestamp_ms: int = 0, user: UserContext = Depends(get_current_user)) -> EngineDetailResponse:
    """Trigger context + live underlying price + per-leg quote/depth/greeks for a
    ready signal (BUY/SELL are placed via the standard /kite/orders endpoint)."""
    client = await _client(user)
    d = await build_detail(client, user.user_id, token, timestamp_ms)
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


@router.get("/open-positions", response_model=OpenPositionsResponse)
async def open_positions(user: UserContext = Depends(get_current_user)) -> OpenPositionsResponse:
    """Return the engine's currently tracked open positions including vehicle/direction labels."""
    uid = user.user_id
    records = [
        OpenPositionRecord(
            symbol=p.symbol, exchange=p.exchange, token=p.token,
            qty=p.qty, lot_size=p.lot_size,
            entry_premium=p.entry_premium, fill_price=p.fill_price,
            stop_premium=p.stop_premium, status=p.status,
            direction=p.direction, vehicle=p.vehicle, underlying=p.underlying,
            opened_ms=p.opened_ms, exit_reason=p.exit_reason, order_id=p.order_id,
        )
        for p in kite_positions.open_positions(uid)
    ]
    return OpenPositionsResponse(positions=records)


@router.delete("/open-positions/{symbol}", response_model=OpenPositionsResponse)
async def close_position(symbol: str, user: UserContext = Depends(get_current_user)) -> OpenPositionsResponse:
    """Manually close (mark-closed) a tracked position without placing a broker order.
    Cancels any live broker GTT stop before closing, so it can't fire after removal.
    Use when an order was filled outside the engine or to clean up stale entries."""
    uid = user.user_id
    from app.services.kite_engine import protective_stop as pstop
    from app.services.exchanges.kite import ticker_manager
    p = kite_positions.get(uid, symbol)
    if p:
        try:
            client = await _client(user)
            if p.gtt_id:
                await pstop.cancel_stop(client, p.gtt_id)
            if p.token:
                await ticker_manager.unsubscribe(uid, [p.token])
        except Exception:  # noqa: BLE001
            pass
    kite_positions.close(uid, symbol, reason="manual_close")
    records = [
        OpenPositionRecord(
            symbol=p.symbol, exchange=p.exchange, token=p.token,
            qty=p.qty, lot_size=p.lot_size,
            entry_premium=p.entry_premium, fill_price=p.fill_price,
            stop_premium=p.stop_premium, status=p.status,
            direction=p.direction, vehicle=p.vehicle, underlying=p.underlying,
            opened_ms=p.opened_ms, exit_reason=p.exit_reason, order_id=p.order_id,
        )
        for p in kite_positions.open_positions(uid)
    ]
    return OpenPositionsResponse(positions=records)


@router.get("/stock-registry")
async def stock_registry() -> list[dict]:
    """Return the curated stock registry with liquidity / volatility metadata,
    plus a separate optional-stocks group for the '+' picker."""
    from app.services.kite_engine.stock_registry import OPTIONAL_STOCKS, STOCK_REGISTRY, STOCKS_BY_LIQUIDITY
    groups = [
        {"liquidity": liq, "stocks": [e.to_dict() for e in entries]}
        for liq in ["Very High", "High", "Good"]
        if liq in STOCKS_BY_LIQUIDITY
        for entries in [STOCKS_BY_LIQUIDITY[liq]]
    ]
    groups.append({"liquidity": "optional", "stocks": [e.to_dict() for e in OPTIONAL_STOCKS]})
    return groups
