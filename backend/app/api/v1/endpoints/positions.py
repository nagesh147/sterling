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

from app.schemas.execution import CandidateContract


def _dte_from_expiry(expiry_date: str) -> int:
    """Compute current DTE from Deribit-style expiry string like '27DEC24'."""
    try:
        dt = datetime.strptime(expiry_date, "%d%b%y").replace(tzinfo=timezone.utc)
        return max(0, (dt - datetime.now(timezone.utc)).days)
    except Exception:
        return -1


def _net_delta(sized_trade) -> float:
    """
    Net delta magnitude for P&L approximation.

    All spread types in structure_selector.py place the higher-delta leg first:
      bull_call_spread  → legs[0]=long lower call (Δ≈0.45), legs[1]=short higher call (Δ≈0.30)
      bear_put_spread   → legs[0]=long higher put (|Δ|≈0.45), legs[1]=short lower put (|Δ|≈0.25)
      bull_put_spread   → legs[0]=short higher put (|Δ|≈0.40), legs[1]=long lower put (|Δ|≈0.20)
      bear_call_spread  → legs[0]=short lower call (Δ≈0.40), legs[1]=long higher call (Δ≈0.20)

    Net = abs(legs[0].delta) - abs(legs[1].delta) for all spreads.
    """
    legs = sized_trade.structure.legs
    if not legs:
        return 0.0
    if len(legs) == 1:
        return abs(legs[0].delta)
    return max(0.0, abs(legs[0].delta) - abs(legs[1].delta))


def _estimate_pnl(
    sized_trade,
    spot_move: float,
    direction_sign: int,
    max_risk_usd: float,
    max_gain_usd: Optional[float],
) -> float:
    """Net-delta-approximated P&L capped by defined risk bounds."""
    contracts = sized_trade.contracts
    net_delta = _net_delta(sized_trade)
    raw = spot_move * direction_sign * contracts * net_delta
    bounded = max(-max_risk_usd, raw)
    if max_gain_usd is not None:
        bounded = min(max_gain_usd * contracts, bounded)
    return round(bounded, 2)
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
        open_count=sum(1 for p in positions if p.status.value in ("open", "partially_closed")),
        partially_closed_count=sum(1 for p in positions if p.status.value == "partially_closed"),
        closed_count=sum(1 for p in positions if p.status.value == "closed"),
    )


@router.get("/summary", response_model=PortfolioSummary)
async def portfolio_summary() -> PortfolioSummary:
    now_ms = int(time.time() * 1000)
    positions = paper_store.list_positions()
    # partially_closed positions still carry open risk — include them
    open_positions = [p for p in positions if p.status.value in ("open", "partially_closed")]
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

    partially_closed = [p for p in positions if p.status.value == "partially_closed"]
    return PortfolioSummary(
        open_count=len(open_positions),
        partially_closed_count=len(partially_closed),
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
    """
    Aggregate net Greeks from open paper positions.
    Delta uses stored per-leg value; gamma/vega/theta are computed via BS
    using the entry IV (mark_iv) and remaining DTE.
    """
    from app.engines.backtest.bs_pricing import bs_gamma, bs_vega, bs_theta
    open_pos = [p for p in paper_store.list_positions() if p.status.value in ("open", "partially_closed")]
    total_delta = 0.0
    total_gamma = 0.0
    total_vega = 0.0
    total_theta = 0.0
    per_position = []

    for pos in open_pos:
        direction_sign = 1 if pos.sized_trade.structure.direction.value == "long" else -1
        contracts = pos.sized_trade.contracts
        pos_delta = pos_gamma = pos_vega = pos_theta = 0.0

        for leg in pos.sized_trade.structure.legs:
            n = contracts * direction_sign
            spot = pos.entry_spot_price
            strike = leg.strike
            dte = max(1, _dte_from_expiry(leg.expiry_date) if _dte_from_expiry(leg.expiry_date) >= 0 else leg.dte)
            iv = (leg.mark_iv or 0.0) / 100.0 if (leg.mark_iv or 0.0) > 1.0 else (leg.mark_iv or 0.0)
            opt_type = leg.option_type if hasattr(leg, "option_type") else "call"

            pos_delta += (leg.delta or 0.0) * n
            if iv > 0 and spot > 0 and strike > 0:
                pos_gamma += bs_gamma(spot, strike, dte, iv) * n
                pos_vega  += bs_vega(spot, strike, dte, iv) * n
                pos_theta += bs_theta(spot, strike, dte, iv, opt_type) * n

        total_delta += pos_delta
        total_gamma += pos_gamma
        total_vega  += pos_vega
        total_theta += pos_theta
        per_position.append({
            "id": pos.id,
            "underlying": pos.underlying,
            "delta": round(pos_delta, 4),
            "gamma": round(pos_gamma, 6),
            "vega": round(pos_vega, 6),
            "theta": round(pos_theta, 6),
        })

    exposure = "bullish" if total_delta > 0.05 else ("bearish" if total_delta < -0.05 else "neutral")
    return {
        "total_delta": round(total_delta, 4),
        "total_gamma": round(total_gamma, 6),
        "total_vega": round(total_vega, 6),
        "total_theta": round(total_theta, 6),
        "net_directional_exposure": exposure,
        "open_positions": len(open_pos),
        "per_position": per_position,
        "timestamp_ms": int(time.time() * 1000),
    }


@router.get("/pnl-live")
async def live_pnl(request: Request):
    """
    Lightweight current P&L for all active positions.
    Uses latest spot price from cache — no candle fetch, no exit evaluation.
    """
    from app.services import adapter_manager as _adm
    now_ms = int(time.time() * 1000)
    active = [
        p for p in paper_store.list_positions()
        if p.status.value in ("open", "partially_closed")
    ]
    if not active:
        return {"positions": [], "total_estimated_pnl_usd": 0.0, "timestamp_ms": now_ms}

    adapter = _adm.get_adapter() or request.app.state.adapter
    from app.services.exchanges import instrument_registry as registry

    results = []
    total_pnl = 0.0

    # Fetch spot prices in parallel
    insts = {p.underlying: registry.get_instrument(p.underlying) for p in active}
    spots: dict = {}
    import asyncio as _asyncio

    async def _fetch_spot(sym: str, inst):
        try:
            spots[sym] = float(await adapter.get_index_price(inst))
        except Exception:
            spots[sym] = None

    await _asyncio.gather(*[
        _fetch_spot(sym, inst)
        for sym, inst in insts.items()
        if inst is not None
    ])

    for pos in active:
        spot = spots.get(pos.underlying)
        leg = pos.sized_trade.structure.legs[0] if pos.sized_trade.structure.legs else None
        dte_from_expiry = _dte_from_expiry(leg.expiry_date) if leg else -1
        if dte_from_expiry >= 0:
            current_dte = dte_from_expiry
        else:
            days_elapsed = int((now_ms - pos.entry_timestamp_ms) / 86_400_000)
            current_dte = max(0, (leg.dte if leg else 0) - days_elapsed)

        pnl = None
        if spot is not None:
            spot_move = spot - pos.entry_spot_price
            direction_sign = 1 if pos.sized_trade.structure.direction.value == "long" else -1
            pnl = _estimate_pnl(
                pos.sized_trade, spot_move, direction_sign,
                pos.sized_trade.max_risk_usd,
                pos.sized_trade.structure.max_gain,
            )
            total_pnl += pnl

        results.append({
            "position_id": pos.id,
            "underlying": pos.underlying,
            "status": pos.status.value,
            "current_spot": spot,
            "entry_spot": pos.entry_spot_price,
            "estimated_pnl_usd": pnl,
            "current_dte": current_dte,
            "max_risk_usd": pos.sized_trade.max_risk_usd,
            "capital_at_risk_pct": pos.sized_trade.capital_at_risk_pct,
        })

    return {
        "positions": results,
        "total_estimated_pnl_usd": round(total_pnl, 2),
        "timestamp_ms": now_ms,
    }


@router.post("/close-all")
async def close_all_positions(request: Request) -> dict:
    """
    Close all open/partially_closed positions using current spot prices.
    Returns count of positions closed and total realized P&L.
    """
    from app.services import adapter_manager as _adm
    now_ms = int(time.time() * 1000)
    active = [
        p for p in paper_store.list_positions()
        if p.status.value in ("open", "partially_closed")
    ]
    if not active:
        return {"closed_count": 0, "total_realized_pnl_usd": 0.0, "timestamp_ms": now_ms}

    adapter = _adm.get_adapter() or request.app.state.adapter
    from app.services.exchanges import instrument_registry as registry
    import asyncio as _asyncio

    spots: dict = {}
    async def _fetch(sym: str, inst):
        try:
            spots[sym] = float(await adapter.get_index_price(inst))
        except Exception:
            spots[sym] = None

    insts = {p.underlying: registry.get_instrument(p.underlying) for p in active}
    await _asyncio.gather(*[_fetch(sym, inst) for sym, inst in insts.items() if inst])

    closed_count = 0
    total_pnl = 0.0
    for pos in active:
        spot = spots.get(pos.underlying) or pos.entry_spot_price
        closed = paper_store.close_position(pos.id, float(spot))
        if closed:
            closed_count += 1
            if closed.realized_pnl_usd is not None:
                total_pnl += closed.realized_pnl_usd

    return {
        "closed_count": closed_count,
        "total_realized_pnl_usd": round(total_pnl, 2),
        "timestamp_ms": now_ms,
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
    from app.api.v1.endpoints.directional import _adapter_can_serve
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(
            status_code=400,
            detail=f"{sym} is not available on {src} data source",
        )
    adapter = _adm.get_adapter() or request.app.state.adapter
    result = await engine_run_once(inst, adapter, get_runtime_risk())

    if result.recommendation == "no_trade" or not result.ranked_structures:
        raise HTTPException(
            status_code=409,
            detail=f"No trade recommended for {sym}: {result.reason}",
        )

    rank = max(0, min(body.structure_rank, len(result.ranked_structures) - 1))
    best_sized = result.ranked_structures[rank]
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

    _sem = asyncio.Semaphore(3)  # cap concurrent adapter calls

    async def _monitor_one(pos: PaperPosition) -> Optional[MonitorResult]:
        async with _sem:
            try:
                inst = registry.get_instrument(pos.underlying)
                if not inst:
                    return None
                adapter = _live_adapter
                c1h = await adapter.get_candles(inst, "1H", limit=200)
                signal = compute_signal(c1h)
                current_spot = await adapter.get_index_price(inst)
                leg = pos.sized_trade.structure.legs[0] if pos.sized_trade.structure.legs else None
                dte_from_expiry = _dte_from_expiry(leg.expiry_date) if leg else -1
                if dte_from_expiry >= 0:
                    current_dte = dte_from_expiry
                else:
                    days_elapsed = int((now_ms - pos.entry_timestamp_ms) / 86_400_000)
                    current_dte = max(0, (leg.dte if leg else 0) - days_elapsed)
                spot_move = current_spot - pos.entry_spot_price
                direction_sign = 1 if pos.sized_trade.structure.direction.value == "long" else -1
                estimated_pnl = _estimate_pnl(
                    pos.sized_trade, spot_move, direction_sign,
                    pos.sized_trade.max_risk_usd,
                    pos.sized_trade.structure.max_gain,
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
    dte_from_expiry = _dte_from_expiry(leg.expiry_date) if leg else -1
    if dte_from_expiry >= 0:
        current_dte = dte_from_expiry
    else:
        days_elapsed = int((now_ms - pos.entry_timestamp_ms) / 86_400_000)
        current_dte = max(0, (leg.dte if leg else 0) - days_elapsed)
    spot_move = current_spot - pos.entry_spot_price
    direction_sign = 1 if pos.sized_trade.structure.direction.value == "long" else -1
    estimated_pnl = _estimate_pnl(
        pos.sized_trade, spot_move, direction_sign,
        pos.sized_trade.max_risk_usd,
        pos.sized_trade.structure.max_gain,
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
