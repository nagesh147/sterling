"""
Paper position endpoints.
Route ordering: ALL literal paths before /{pos_id} to prevent shadowing.
"""
import asyncio
import csv
import io
import math
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse

from app.schemas.positions import (
    PaperPosition, PositionListResponse, PositionStatus,
    EnterPositionRequest, ClosePositionRequest,
    MonitorResult, MonitorAllResult, PortfolioSummary,
    TradeAnalytics,
)
from app.schemas.risk import ExitSignal
from app.services import paper_store, pnl_history
from app.services.exchanges import instrument_registry as registry
from app.engines.directional.orchestrator import run_once as engine_run_once
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.monitor_engine import check_exits
from app.schemas.directional import TradeState

router = APIRouter(prefix="/positions", tags=["positions"])


# ─── Collection endpoints (no path param) ────────────────────────────────────

@router.get("", response_model=PositionListResponse)
async def list_positions(
    underlying: str = Query(default=""),
    status: str = Query(default=""),
) -> PositionListResponse:
    positions = paper_store.list_positions()
    if underlying.strip():
        positions = [p for p in positions if p.underlying == underlying.upper()]
    if status.strip():
        positions = [p for p in positions if p.status.value == status.lower()]
    return PositionListResponse(
        positions=positions,
        open_count=sum(1 for p in positions if p.status.value == "open"),
        closed_count=sum(1 for p in positions if p.status.value == "closed"),
    )


@router.get("/summary", response_model=PortfolioSummary)
async def portfolio_summary() -> PortfolioSummary:
    now_ms = int(time.time() * 1000)
    positions = paper_store.list_positions()
    open_positions = [p for p in positions if p.status.value == "open"]
    closed_positions = [p for p in positions if p.status.value == "closed"]

    total_open_risk = sum(p.sized_trade.max_risk_usd for p in open_positions)
    largest_open_risk = max((p.sized_trade.max_risk_usd for p in open_positions), default=0.0)
    total_realized_pnl = sum(
        p.realized_pnl_usd for p in closed_positions if p.realized_pnl_usd is not None
    )
    avg_risk_pct = (
        sum(p.sized_trade.capital_at_risk_pct for p in open_positions) / len(open_positions)
        if open_positions else 0.0
    )

    return PortfolioSummary(
        open_count=len(open_positions),
        closed_count=len(closed_positions),
        total_positions=len(positions),
        total_open_risk_usd=round(total_open_risk, 2),
        total_realized_pnl_usd=round(total_realized_pnl, 2),
        largest_open_risk_usd=round(largest_open_risk, 2),
        underlyings_open=sorted({p.underlying for p in open_positions}),
        avg_capital_at_risk_pct=round(avg_risk_pct, 3),
        timestamp_ms=now_ms,
    )


@router.get("/analytics", response_model=TradeAnalytics)
async def trade_analytics() -> TradeAnalytics:
    """Win rate, avg P&L, profit factor across all closed positions."""
    now_ms = int(time.time() * 1000)
    closed = [p for p in paper_store.list_positions() if p.status.value == "closed"]
    pnls = [p.realized_pnl_usd for p in closed if p.realized_pnl_usd is not None]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]

    gross_win = sum(winners) if winners else 0.0
    gross_loss = abs(sum(losers)) if losers else 0.0
    # Use 999.9 as sentinel for ∞ (Infinity is not valid JSON)
    if gross_loss > 0:
        pf = round(gross_win / gross_loss, 2)
    elif gross_win > 0:
        pf = 999.9
    else:
        pf = 0.0

    return TradeAnalytics(
        total_closed=len(closed),
        winners=len(winners),
        losers=len(losers),
        win_rate_pct=round(len(winners) / max(1, len(pnls)) * 100, 1),
        avg_pnl_usd=round(sum(pnls) / max(1, len(pnls)), 2),
        avg_winner_usd=round(sum(winners) / max(1, len(winners)), 2) if winners else 0.0,
        avg_loser_usd=round(sum(losers) / max(1, len(losers)), 2) if losers else 0.0,
        best_trade_usd=max(pnls) if pnls else 0.0,
        worst_trade_usd=min(pnls) if pnls else 0.0,
        total_realized_pnl_usd=round(sum(pnls), 2),
        profit_factor=pf,
        timestamp_ms=now_ms,
    )


@router.get("/greeks")
async def paper_portfolio_greeks():
    """Aggregate delta from open paper positions — net directional exposure."""
    open_pos = [p for p in paper_store.list_positions() if p.status.value == "open"]
    total_delta = 0.0
    for pos in open_pos:
        direction_sign = 1 if pos.sized_trade.structure.direction.value == "long" else -1
        for leg in pos.sized_trade.structure.legs:
            total_delta += (leg.delta or 0.0) * pos.sized_trade.contracts * direction_sign
    total_delta = round(total_delta, 4)
    exposure = "bullish" if total_delta > 0.05 else ("bearish" if total_delta < -0.05 else "neutral")
    return {
        "total_delta": total_delta,
        "net_directional_exposure": exposure,
        "open_positions": len(open_pos),
        "timestamp_ms": int(time.time() * 1000),
    }


@router.get("/export")
async def export_positions_csv(status: str = Query(default="")) -> StreamingResponse:
    """Export paper positions as CSV."""
    positions = paper_store.list_positions()
    if status.strip():
        positions = [p for p in positions if p.status.value == status.lower()]

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "underlying", "structure_type", "direction", "status",
                "entry_spot", "exit_spot", "contracts", "max_risk_usd",
                "realized_pnl_usd", "entry_time", "exit_time", "notes"])
    for p in positions:
        s = p.sized_trade.structure
        entry_dt = datetime.fromtimestamp(p.entry_timestamp_ms / 1000, tz=timezone.utc).isoformat()
        exit_dt = (datetime.fromtimestamp(p.exit_timestamp_ms / 1000, tz=timezone.utc).isoformat()
                   if p.exit_timestamp_ms else "")
        w.writerow([p.id, p.underlying, s.structure_type, s.direction.value, p.status.value,
                    p.entry_spot_price, p.exit_spot_price or "", p.sized_trade.contracts,
                    p.sized_trade.max_risk_usd, p.realized_pnl_usd or "",
                    entry_dt, exit_dt, p.notes])

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sterling_paper_positions.csv"'},
    )


@router.post("/enter", response_model=PaperPosition)
async def enter_position(body: EnterPositionRequest, request: Request) -> PaperPosition:
    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    from app.services import adapter_manager as _adm
    from app.api.v1.endpoints.config import get_runtime_risk
    adapter = _adm.get_adapter() or request.app.state.adapter
    result = await engine_run_once(inst, adapter, get_runtime_risk())

    if result.recommendation == "no_trade" or not result.ranked_structures:
        raise HTTPException(
            status_code=409,
            detail=f"No trade recommended for {sym}: {result.reason}",
        )

    best_sized = result.ranked_structures[0]
    try:
        spot_price = await adapter.get_index_price(inst)
    except Exception:
        spot_price = best_sized.structure.legs[0].mark_price if best_sized.structure.legs else 0.0

    return paper_store.add_position(
        underlying=sym,
        sized_trade=best_sized,
        entry_spot_price=spot_price,
        notes=body.notes,
    )


@router.post("/monitor-all", response_model=MonitorAllResult)
async def monitor_all(request: Request) -> MonitorAllResult:
    now_ms = int(time.time() * 1000)
    # Include partially_closed positions — still need monitoring
    active_positions = [
        p for p in paper_store.list_positions()
        if p.status.value in ("open", "partially_closed")
    ]

    from app.api.v1.endpoints.config import get_runtime_risk
    risk = get_runtime_risk()

    from app.services import adapter_manager as _adm
    _live_adapter = _adm.get_adapter() or request.app.state.adapter

    async def _monitor_one(pos: PaperPosition) -> Optional[MonitorResult]:
        try:
            inst = registry.get_instrument(pos.underlying)
            if not inst:
                return None
            adapter = _live_adapter
            c1h = await adapter.get_candles(inst, "1H", limit=200)
            signal = compute_signal(c1h)
            current_spot = await adapter.get_index_price(inst)
            leg = pos.sized_trade.structure.legs[0] if pos.sized_trade.structure.legs else None
            days_elapsed = int((now_ms - pos.entry_timestamp_ms) / 86_400_000)
            current_dte = max(0, (leg.dte if leg else 0) - days_elapsed)
            spot_move = current_spot - pos.entry_spot_price
            direction_sign = 1 if pos.sized_trade.structure.direction.value == "long" else -1
            estimated_pnl = round(
                spot_move * direction_sign * pos.sized_trade.contracts * abs(leg.delta if leg else 0), 2
            )
            exit_signal = check_exits(
                pos.sized_trade, signal, estimated_pnl, current_dte,
                force_exit_dte=inst.force_exit_dte,
                financial_stop_pct=risk.financial_stop_pct,
                partial_profit_r1=risk.partial_profit_r1,
                partial_profit_r2=risk.partial_profit_r2,
            )
            pnl_history.record(pos.id, current_spot, estimated_pnl, current_dte, now_ms)

            # Auto-execute: full exit → close position
            if exit_signal.should_exit and not exit_signal.partial:
                paper_store.close_position(pos.id, float(current_spot))
            # Auto-execute: partial → transition to PARTIALLY_CLOSED
            elif exit_signal.partial and pos.status == PositionStatus.OPEN:
                paper_store.partial_close_position(pos.id)

            return MonitorResult(
                position_id=pos.id, underlying=pos.underlying,
                exit_signal=exit_signal, current_spot=current_spot,
                estimated_pnl_usd=estimated_pnl, current_dte=current_dte,
                current_signal_trend=signal.trend, timestamp_ms=now_ms,
            )
        except Exception:
            return None

    raw = await asyncio.gather(*[_monitor_one(p) for p in active_positions])
    results = [r for r in raw if r is not None]
    exit_ids = [r.position_id for r in results if r.exit_signal.should_exit and not r.exit_signal.partial]
    partial_ids = [r.position_id for r in results if r.exit_signal.partial]

    return MonitorAllResult(
        open_positions_checked=len(active_positions),
        exit_recommended=exit_ids,
        partial_recommended=partial_ids,
        results=results,
        timestamp_ms=now_ms,
    )


# ─── Single-position endpoints (path param LAST) ─────────────────────────────

@router.get("/{pos_id}/pnl-history")
async def get_pnl_history(pos_id: str):
    """Session P&L snapshots for a position — recorded on each monitor call."""
    snapshots = pnl_history.get_history(pos_id.upper())
    return {
        "position_id": pos_id.upper(),
        "snapshots": [s.model_dump() for s in snapshots],
        "count": len(snapshots),
    }


@router.patch("/{pos_id}/notes", response_model=PaperPosition)
async def update_position_notes(pos_id: str, notes: str = "") -> PaperPosition:
    """Update trade journal notes for a paper position."""
    pos = paper_store.update_position(pos_id.upper(), notes=notes)
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {pos_id} not found")
    return pos


@router.get("/{pos_id}", response_model=PaperPosition)
async def get_position(pos_id: str) -> PaperPosition:
    pos = paper_store.get_position(pos_id.upper())
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {pos_id} not found")
    return pos


@router.post("/{pos_id}/close", response_model=PaperPosition)
async def close_position(pos_id: str, body: ClosePositionRequest) -> PaperPosition:
    updated = paper_store.close_position(pos_id.upper(), body.exit_spot_price, body.notes)
    if not updated:
        raise HTTPException(
            status_code=404, detail=f"Position {pos_id} not found or already closed"
        )
    return updated


@router.post("/{pos_id}/monitor", response_model=MonitorResult)
async def monitor_position(pos_id: str, request: Request) -> MonitorResult:
    pos = paper_store.get_position(pos_id.upper())
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {pos_id} not found")
    if pos.status.value not in ("open", "partially_closed"):
        raise HTTPException(status_code=409, detail="Position already fully closed")

    inst = registry.get_instrument(pos.underlying)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {pos.underlying}")

    from app.services import adapter_manager as _adm
    adapter = _adm.get_adapter() or request.app.state.adapter
    now_ms = int(time.time() * 1000)

    try:
        c1h = await adapter.get_candles(inst, "1H", limit=200)
        signal = compute_signal(c1h)
        current_spot = await adapter.get_index_price(inst)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {exc}")

    leg = pos.sized_trade.structure.legs[0] if pos.sized_trade.structure.legs else None
    days_elapsed = int((now_ms - pos.entry_timestamp_ms) / 86_400_000)
    current_dte = max(0, (leg.dte if leg else 0) - days_elapsed)
    spot_move = current_spot - pos.entry_spot_price
    direction_sign = 1 if pos.sized_trade.structure.direction.value == "long" else -1
    estimated_pnl = round(
        spot_move * direction_sign * pos.sized_trade.contracts * abs(leg.delta if leg else 0), 2
    )
    from app.api.v1.endpoints.config import get_runtime_risk
    risk = get_runtime_risk()
    exit_signal = check_exits(
        pos.sized_trade, signal, estimated_pnl, current_dte,
        force_exit_dte=inst.force_exit_dte,
        financial_stop_pct=risk.financial_stop_pct,
        partial_profit_r1=risk.partial_profit_r1,
        partial_profit_r2=risk.partial_profit_r2,
    )

    # Record P&L snapshot for session history
    pnl_history.record(pos.id, current_spot, estimated_pnl, current_dte, now_ms)

    # Auto-execute: full exit → close position
    if exit_signal.should_exit and not exit_signal.partial:
        paper_store.close_position(pos.id, float(current_spot))
    # Auto-execute: partial → transition to PARTIALLY_CLOSED
    elif exit_signal.partial and pos.status == PositionStatus.OPEN:
        paper_store.partial_close_position(pos.id)

    return MonitorResult(
        position_id=pos.id, underlying=pos.underlying,
        exit_signal=exit_signal, current_spot=current_spot,
        estimated_pnl_usd=estimated_pnl, current_dte=current_dte,
        current_signal_trend=signal.trend, timestamp_ms=now_ms,
    )


@router.delete("/{pos_id}", status_code=204)
async def delete_position(pos_id: str) -> None:
    if not paper_store.delete_position(pos_id.upper()):
        raise HTTPException(status_code=404, detail=f"Position {pos_id} not found")
