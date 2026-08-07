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
from typing import Any, Optional

from pydantic import BaseModel

from app.core.logging import get_logger
from app.schemas.execution import CandidateContract

log = get_logger(__name__)


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

    Futures structures have an empty `legs` list (no option leg) and a 1:1
    linear exposure to spot, so their net delta is the leverage multiplier.
    Pre-v4 this function returned 0.0 for empty legs, which made
    `_estimate_pnl` always return 0.0 for futures positions and the
    "Open P/L" widget was permanently stuck at zero — fix is to detect the
    futures structure_type and return leverage as the effective delta.

    For option spreads, the higher-delta leg goes first by construction
    (see `structure_selector.build_structures`), so net = |leg[0].δ| − |leg[1].δ|.

      bull_call_spread  → legs[0]=long lower call (Δ≈0.45), legs[1]=short higher call (Δ≈0.30)
      bear_put_spread   → legs[0]=long higher put (|Δ|≈0.45), legs[1]=short lower put (|Δ|≈0.25)
      bull_put_spread   → legs[0]=short higher put (|Δ|≈0.40), legs[1]=long lower put (|Δ|≈0.20)
      bear_call_spread  → legs[0]=short lower call (Δ≈0.40), legs[1]=long higher call (Δ≈0.20)
    """
    legs = sized_trade.structure.legs
    stype = getattr(sized_trade.structure, "structure_type", "").lower()
    if not legs:
        # Legacy futures/spot with no legs — leverage = effective linear delta.
        if stype in ("futures", "spot", "perp"):
            return float(getattr(sized_trade.structure, "leverage", 1) or 1)
        return 0.0
    if stype in ("futures", "spot", "perp"):
        # Derivatives-engine futures carry a SINGLE placeholder leg whose
        # option-delta is 0. It's a delta-1 LINEAR instrument and qty already
        # holds the full coin quantity, so net delta is 1.0 — NOT the leg's 0
        # (which made _estimate_pnl return 0 and stuck the futures "Open P/L"
        # at zero for every futures position).
        return 1.0
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
    # qty = coin quantity = lots × lot size (cv defaults to 1.0, so legacy
    # coin-based positions are unchanged). Exposure scales with qty, never the
    # raw exchange lot count — a Delta ETH position of 42 lots × 0.01 is 0.42 ETH.
    qty = sized_trade.qty
    net_delta = _net_delta(sized_trade)
    raw = spot_move * direction_sign * qty * net_delta
    bounded = max(-max_risk_usd, raw)
    if max_gain_usd is not None:
        bounded = min(max_gain_usd * qty, bounded)
    return round(bounded, 2)


def _funding_cost_usd(funding_8h_pct: float, notional_usd: float,
                      hours_held: float) -> float:
    """Funding cost accrued on a perp/futures position since entry:
    |rate| × notional × settlements_elapsed (one settlement per 8h). Returns
    0 for a just-entered position or when no funding rate is available — these
    are the cases that left the futures "Funding" column showing 0."""
    if not funding_8h_pct or notional_usd <= 0 or hours_held <= 0:
        return 0.0
    settlements = hours_held / 8.0
    return round(abs(funding_8h_pct) * notional_usd * settlements, 2)


def _theta_burn_usd(legs, contracts: float, hold_days: float) -> float:
    """Projected net theta decay over the remaining hold for an option
    structure: |net theta| × contracts × hold_days, where net theta sums each
    leg's theta signed by side (buy +, sell −) so a spread's short leg offsets
    the long leg. Returns 0 for futures (no legs / no option theta)."""
    if not legs or contracts <= 0 or hold_days <= 0:
        return 0.0
    net_theta = sum((getattr(l, "theta", 0.0) or 0.0)
                    * (1.0 if getattr(l, "side", "buy") == "buy" else -1.0)
                    for l in legs)
    return round(abs(net_theta) * contracts * hold_days, 2)

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
from app.services.exchange_account_store import list_exchanges as _list_exchange_configs
from app.services.exchanges import instrument_registry as registry
from app.engines.directional.orchestrator import run_once as engine_run_once


# Reusable helper extracted for red-count exit logic in monitor flows (directional + for parity with kite).
# Called from _monitor_one (and usable in tests/kite). Supports greeks/trail flags for monitor integration.
def _compute_red_and_maybe_close(
    pos: "PaperPosition",
    signal: Any,
    current_spot: float,
    now_ms: int,
    estimated_pnl: float,
    current_dte: int,
    update_greeks: bool = False,
    trail_update: bool = False,
) -> Optional["MonitorResult"]:
    """Compute red from st_trends, update store if changed, close pos on exit per mode.
    Returns MonitorResult on exit or None. Shared logic for parity.
    """
    if getattr(pos, "exit_mode", None) and hasattr(signal, "st_trends"):
        try:
            from app.engines.common.exit_counter import (
                compute_red_count_from_trends,
                get_exit_threshold,
                should_exit_on_reds,
            )
            d = pos.sized_trade.structure.direction.value
            rc = compute_red_count_from_trends(
                signal.st_trends or [getattr(signal, "trend", 0)] * 3, d
            )
            if rc != getattr(pos, "current_red_count", 0):
                paper_store.update_position(pos.id, current_red_count=rc)
            thresh = get_exit_threshold(pos.exit_mode)
            if should_exit_on_reds(rc, pos.exit_mode):
                exit_signal = ExitSignal(
                    should_exit=True,
                    reason=f"red_count_exit {rc}/{thresh} ({pos.exit_mode})",
                    exit_type="red_count",
                )
                paper_store.close_position(pos.id, float(current_spot))
                return MonitorResult(
                    position_id=pos.id,
                    underlying=pos.underlying,
                    exit_signal=exit_signal,
                    current_spot=current_spot,
                    estimated_pnl_usd=estimated_pnl,
                    current_dte=current_dte,
                    current_signal_trend=getattr(signal, "trend", None),
                    timestamp_ms=now_ms,
                )
        except Exception:
            pass
    return None


def _is_paper_mode() -> bool:
    """True when no active exchange is in live mode. Defaults to True (paper) on error or no configs."""
    try:
        active = [cfg for cfg in _list_exchange_configs() if cfg.is_active]
        if not active:
            return True  # no active exchanges → safe default to paper
        return all(cfg.is_paper for cfg in active)
    except Exception:
        return True
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.monitor_engine import check_exits

router = APIRouter(prefix="/positions", tags=["positions"])

# Concurrency guard: serialises the open_count-check + add_position critical section.
_enter_lock = asyncio.Lock()


# ─── Collection endpoints (no path param) ────────────────────────────────────

@router.get("")
async def list_positions(
    underlying: str = Query(default=""),
    status: str = Query(default=""),
    mode: str = Query(default=""),   # "paper" | "live" — filter by trading mode
) -> PositionListResponse:
    positions = paper_store.list_positions()
    if underlying.strip():
        positions = [p for p in positions if p.underlying == underlying.upper()]
    if status.strip():
        positions = [p for p in positions if p.status.value == status.lower()]
    if mode.strip() == "paper":
        positions = [p for p in positions if p.is_paper]
    elif mode.strip() == "live":
        positions = [p for p in positions if not p.is_paper]
    return PositionListResponse(
        positions=positions,
        open_count=sum(1 for p in positions if p.status.value in ("open", "partially_closed")),
        partially_closed_count=sum(1 for p in positions if p.status.value == "partially_closed"),
        closed_count=sum(1 for p in positions if p.status.value == "closed"),
    )


@router.get("/summary")
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


@router.get("/analytics")
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


@router.get("/analytics/performance")
async def trade_analytics_performance() -> dict:
    """Extended performance metrics: Sharpe, Calmar, Sortino, max DD, regime breakdown."""
    import numpy as np
    from app.services import db as _db
    from app.engines.analytics.performance import full_report

    closed = _db.get_closed_positions_for()
    snapshots = _db.get_equity_snapshots(limit=1000)

    # Issue 17 — filter rows with corrupt entry_spot_price (= 0 or missing).
    # Pre-TTACE seed data has rows where entry_spot_price == 0 which fabricates
    # nonsense "wins" through the pnl_pct = pnl / entry_spot division.
    trades = []
    corrupt_row_count = 0
    for pos in closed:
        entry_spot_raw = pos.get('entry_spot_price', 0.0)
        try:
            entry_spot = float(entry_spot_raw or 0.0)
        except (TypeError, ValueError):
            entry_spot = 0.0
        if entry_spot <= 0:
            corrupt_row_count += 1
            continue
        pnl = pos.get('realized_pnl_usd', 0.0) or 0.0
        pnl_pct = pnl / max(entry_spot * 10, 1.0)
        regime = pos.get('regime', 'unknown') or 'unknown'
        trades.append({'pnl_pct': float(pnl_pct), 'regime': str(regime)})

    vals = [s.get('portfolio_value', 1.0) for s in reversed(snapshots) if s.get('portfolio_value')]
    if len(vals) < 2:
        equity_curve = np.array([1.0, 1.0])
    else:
        base = vals[0]
        equity_curve = np.array([v / base for v in vals])

    if len(trades) < 2:
        return {
            'total_trades': len(trades),
            'corrupt_row_count': corrupt_row_count,
            'message': 'Insufficient closed trades for performance metrics',
            'sharpe': 0.0, 'calmar': 0.0, 'sortino': 0.0, 'max_drawdown': 0.0,
            'win_rate': 0.0, 'regime_breakdown': {},
        }

    report = full_report(equity_curve, trades)
    pf = report.profit_factor
    return {
        'sharpe': round(report.sharpe, 4),
        'calmar': round(report.calmar, 4),
        'sortino': round(report.sortino, 4),
        'max_drawdown': round(report.max_drawdown, 4),
        'win_rate': round(report.win_rate, 4),
        'avg_rr': round(report.avg_rr, 4),
        'profit_factor': (None if pf is None
                          else (float('inf') if pf == float('inf')
                                else round(pf, 4))),
        'total_trades': report.total_trades,
        'corrupt_row_count': corrupt_row_count,
        'regime_breakdown': report.regime_breakdown,
        'slippage_adjusted': True,
    }


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
        qty = pos.sized_trade.qty   # coin quantity (cv=1.0 → unchanged for options)
        pos_delta = pos_gamma = pos_vega = pos_theta = 0.0

        for leg in pos.sized_trade.structure.legs:
            n = qty * direction_sign
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

    # Funding rate per underlying (for the futures "Funding" column). Parallel,
    # graceful — a fetch failure leaves funding at 0, never breaks pnl-live.
    fundings: dict = {}

    async def _fetch_funding(sym: str, inst):
        try:
            pid = await adapter.get_product_id(
                getattr(inst, "delta_perp_symbol", None) or f"{sym}USD")
            fr = await adapter.get_funding_rate(pid)
            fundings[sym] = float(fr.get("funding_rate_8h_pct") or 0.0)
        except Exception:
            fundings[sym] = 0.0

    await _asyncio.gather(*[
        _fetch_funding(sym, inst)
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

        trail_state = None
        if pos.trail_stop_json:
            try:
                import json as _json
                trail_state = _json.loads(pos.trail_stop_json)
            except Exception:
                pass

        # Live funding (futures) + theta-burn (options) — recomputed here so the
        # FE columns aren't stuck at 0. Futures pay funding (no option theta);
        # options decay theta (no perp funding).
        struct = pos.sized_trade.structure
        stype = (getattr(struct, "structure_type", "") or "").lower()
        notional = pos.sized_trade.qty * (pos.entry_spot_price or 0.0)
        hours_held = max(0.0, (now_ms - pos.entry_timestamp_ms) / 3_600_000.0)
        if stype in ("futures", "spot", "perp"):
            funding_cost = _funding_cost_usd(
                fundings.get(pos.underlying, 0.0), notional, hours_held)
            theta_burn = 0.0
        else:
            funding_cost = 0.0
            theta_burn = _theta_burn_usd(
                struct.legs, pos.sized_trade.contracts, current_dte)

        results.append({
            "position_id": pos.id,
            "underlying": pos.underlying,
            "status": pos.status.value,
            "current_spot": spot,
            "entry_spot": pos.entry_spot_price,
            "estimated_pnl_usd": pnl,
            "funding_cost_usd": funding_cost,
            "expected_theta_burn_usd": theta_burn,
            "current_dte": current_dte,
            "max_risk_usd": pos.sized_trade.max_risk_usd,
            "capital_at_risk_pct": pos.sized_trade.capital_at_risk_pct,
            "direction": pos.sized_trade.structure.direction.value,
            "contracts": pos.sized_trade.contracts,
            "leverage": getattr(pos.sized_trade.structure, "leverage", 1) or 1,
            "entry_timestamp_ms": pos.entry_timestamp_ms,
            "entry_price_real": pos.entry_price_real,
            "initial_sl": pos.initial_sl,
            "initial_tp": pos.initial_tp,
            "current_sl": pos.current_sl,
            "current_tp": pos.current_tp,
            "trail_mode": pos.trail_mode,
            "trail_state": trail_state,
            "order_id": pos.order_id,
            "order_status": pos.order_status,
            "mode": pos.mode,
            "structure_type": getattr(pos.sized_trade.structure, "structure_type", ""),
        })

    return {
        "positions": results,
        "total_estimated_pnl_usd": round(total_pnl, 2),
        "timestamp_ms": now_ms,
    }


@router.post("/close-all")
async def close_all_positions(request: Request, mode: str = Query(default="")) -> dict:
    """
    Close all open/partially_closed positions using current spot prices.
    Optional `mode` filter — "paper" or "live" — closes only that side, so a
    "Close all paper" action never touches live positions.
    Returns count of positions closed and total realized P&L.
    """
    from app.services import adapter_manager as _adm
    now_ms = int(time.time() * 1000)
    active = [
        p for p in paper_store.list_positions()
        if p.status.value in ("open", "partially_closed")
    ]
    m = mode.strip().lower()
    if m == "paper":
        active = [p for p in active if p.is_paper]
    elif m == "live":
        active = [p for p in active if not p.is_paper]
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


@router.post("/clear-all")
async def clear_all_positions(mode: str = Query(default="")) -> dict:
    """
    Delete CLOSED position records from the tracking store (history cleanup).
    Open/partially-closed positions are kept. Optional `mode` filter
    ("paper" | "live"). Close positions first, then clear their history.
    """
    removed = paper_store.clear_positions(mode)
    return {"removed_count": removed, "timestamp_ms": int(time.time() * 1000)}


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


class DirectEntryRequest(BaseModel):
    underlying: str
    direction: str   # "long" or "short"
    leverage: int = 1
    notes: str = ""


@router.post("/enter-direct")
async def enter_direct_position(body: DirectEntryRequest, request: Request) -> PaperPosition:
    """
    Create a paper futures position directly from signal state.
    Does not require options structures — creates a synthetic futures trade.
    """
    from app.schemas.execution import (
        TradeStructure, CandidateContract, Direction as ExecDir,
    )
    from app.engines.directional.sizing_engine import size_trade
    from app.api.v1.endpoints.config import get_runtime_risk

    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    if body.direction not in ("long", "short"):
        raise HTTPException(status_code=400, detail="direction must be 'long' or 'short'")

    from app.services import adapter_manager as _adm
    adapter = _adm.get_adapter() or request.app.state.adapter
    try:
        spot_price = float(await adapter.get_index_price(inst))
    except Exception:
        try:
            from app.api.v1.endpoints.directional import _stream_last_prices
            spot_price = float(_stream_last_prices.get(sym, 0.0))
        except Exception:
            spot_price = 0.0

    # Synthetic futures leg
    direction = ExecDir.LONG if body.direction == "long" else ExecDir.SHORT
    leg = CandidateContract(
        instrument_name=f"{sym}-PERP",
        underlying=sym,
        strike=spot_price,
        expiry_date="",
        option_type="future",
        bid=spot_price,
        ask=spot_price,
        mark_price=spot_price,
        mid_price=spot_price,
        mark_iv=0.0,
        delta=1.0 if body.direction == "long" else -1.0,
        dte=0,
        open_interest=0.0,
        volume_24h=0.0,
        spread_pct=0.0,
        health_score=100.0,
        healthy=True,
    )
    structure = TradeStructure(
        structure_type="futures",
        direction=direction,
        legs=[leg],
        net_premium=spot_price,
        max_loss=spot_price * 0.03,
        max_gain=None,
        risk_reward=2.0,
        score=0.0,
        score_breakdown={},
    )

    risk = get_runtime_risk()
    sized = size_trade(structure, risk, leverage=body.leverage)

    mode = getattr(request.app.state, "trading_mode", None)
    return paper_store.add_position(
        underlying=sym,
        sized_trade=sized,
        entry_spot_price=spot_price,
        notes=body.notes or f"Direct {body.direction.upper()} entry",
        is_paper=_is_paper_mode(),
        trail_mode_name=mode.name if mode else None,
        trail_atr_mult=mode.trail_atr_mult if mode else 2.0,
    )


@router.post("/enter")
async def enter_position(body: EnterPositionRequest, request: Request) -> PaperPosition:
    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    # Circuit breaker check — compute real daily PnL and margin before calling.
    cb = getattr(request.app.state, "circuit_breaker", None)
    if cb is not None:
        mode = getattr(request.app.state, "trading_mode", None)
        max_conc = mode.max_concurrent if mode else 5
        from app.services.execution.circuit_breaker import CircuitState
        from app.api.v1.endpoints.config import get_runtime_risk as _get_risk

        # Daily PnL: sum realized P&L for positions closed today.
        _capital = _get_risk().capital or 10_000.0
        _today_start_ms = int((time.time() // 86_400) * 86_400 * 1_000)
        _today_closed = [
            p for p in paper_store.list_positions()
            if p.status.value == "closed"
            and p.realized_pnl_usd is not None
            and (p.exit_timestamp_ms or 0) >= _today_start_ms
        ]
        _daily_pnl_usd = sum(p.realized_pnl_usd for p in _today_closed)
        _daily_pnl_pct = _daily_pnl_usd / _capital if _capital > 0 else 0.0

        # Free margin: capital not tied up in open position risk.
        _open_risk = sum(
            p.sized_trade.max_risk_usd for p in paper_store.list_positions()
            if p.status.value in ("open", "partially_closed")
        )
        _free_margin_pct = max(0.0, 1.0 - _open_risk / _capital) if _capital > 0 else 1.0

        check = await cb.check(
            daily_pnl_pct=_daily_pnl_pct,
            free_margin_pct=_free_margin_pct,
            open_count=paper_store.open_count(),
            mode_max_concurrent=max_conc,
        )
        if check.state in (CircuitState.HALTED, CircuitState.NO_NEW_ENTRIES):
            raise HTTPException(status_code=503, detail=check.reason)

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

    # ── DrawdownCircuitBreaker: update portfolio value, get size multiplier ──
    _dd_breaker   = getattr(request.app.state, "dd_circuit_breaker", None)
    _dd_size_mult = 1.0
    if _dd_breaker is not None:
        _risk0   = get_runtime_risk()
        _cap0    = _risk0.capital or 10_000.0
        _all_p0  = paper_store.list_positions()
        _pv0     = _cap0 + sum(
            p.realized_pnl_usd for p in _all_p0
            if p.status.value == "closed" and p.realized_pnl_usd
        )
        _dd_breaker.update(_pv0)
        _dd_size_mult = _dd_breaker.size_multiplier()
        if _dd_size_mult == 0.0:
            raise HTTPException(
                status_code=503,
                detail=f"DrawdownCircuitBreaker {_dd_breaker.state.value} — no new positions",
            )

    # ── Calibration: inject adaptive win_rate into RiskParams for Kelly ──────
    # TTACE Phase 3: when the calibration sample is too small we explicitly
    # mark win_rate_known=False so the sizer fails closed instead of
    # silently sizing off the 0.52 default.
    _risk = get_runtime_risk()
    _cal  = getattr(request.app.state, "calibration_service", None)
    _adaptive_wr = _cal.win_rate() if _cal is not None else None
    if _adaptive_wr is not None and 0.10 <= _adaptive_wr <= 0.90:
        _risk = _risk.model_copy(update={
            "win_rate":       round(_adaptive_wr, 4),
            "win_rate_known": True,
        })
    else:
        _risk = _risk.model_copy(update={"win_rate_known": False})

    result = await engine_run_once(inst, adapter, _risk)

    if result.recommendation == "no_trade" or not result.ranked_structures:
        raise HTTPException(
            status_code=409,
            detail=f"No trade recommended for {sym}: {result.reason}",
        )

    rank       = max(0, min(body.structure_rank, len(result.ranked_structures) - 1))
    best_sized = result.ranked_structures[rank]
    try:
        spot_price = await adapter.get_index_price(inst)
    except Exception:
        spot_price = best_sized.structure.legs[0].mark_price if best_sized.structure.legs else 0.0

    # Apply DD size multiplier to the selected trade
    if _dd_size_mult < 1.0:
        _reduced = max(1, int(best_sized.contracts * _dd_size_mult))
        _scale   = _reduced / max(best_sized.contracts, 1)
        best_sized = best_sized.model_copy(update={
            "contracts":           _reduced,
            "max_risk_usd":        round(best_sized.max_risk_usd        * _scale, 2),
            "position_value":      round(best_sized.position_value      * _scale, 2),
            "capital_at_risk_pct": round(best_sized.capital_at_risk_pct * _scale, 3),
        })

    mode = getattr(request.app.state, "trading_mode", None)

    # ── ATR-based initial SL and TP ───────────────────────────────────────────
    _initial_sl: Optional[float] = None
    _initial_tp: Optional[float] = None
    try:
        import numpy as _np
        from app.engines.indicators.atr import compute_atr as _atr_fn
        _c4h_sl = await adapter.get_candles(inst, "4H", limit=25)
        if len(_c4h_sl) >= 14:
            _h4  = _np.array([c.high  for c in _c4h_sl], dtype=_np.float64)
            _l4  = _np.array([c.low   for c in _c4h_sl], dtype=_np.float64)
            _c4a = _np.array([c.close for c in _c4h_sl], dtype=_np.float64)
            _av4 = _atr_fn(_h4, _l4, _c4a, 14)
            _atr4 = float(_av4[-1]) if len(_av4) > 0 and not _np.isnan(_av4[-1]) else float(spot_price) * 0.02
        else:
            _atr4 = float(spot_price) * 0.02
        _stop_mult  = mode.stop_atr_mult if mode else 2.0
        _rr_mult    = mode.rr_target     if mode else 2.0
        _stop_dist  = _stop_mult * _atr4
        _dir_str    = result.direction.value  # "long" | "short" | "neutral"
        if _dir_str == "long":
            _initial_sl = round(float(spot_price) - _stop_dist, 4)
            _initial_tp = round(float(spot_price) + _rr_mult * _stop_dist, 4)
        elif _dir_str == "short":
            _initial_sl = round(float(spot_price) + _stop_dist, 4)
            _initial_tp = round(float(spot_price) - _rr_mult * _stop_dist, 4)
    except Exception:
        pass  # SL/TP remain None → paper_store falls back to 5%-below

    # ── Concurrency-safe add: lock guards check + add atomically ─────────────
    async with _enter_lock:
        _mode_inner   = getattr(request.app.state, "trading_mode", None)
        _max_conc_now = _mode_inner.max_concurrent if _mode_inner else 5
        if paper_store.open_count() >= _max_conc_now:
            raise HTTPException(
                status_code=409,
                detail=f"Max concurrent positions ({_max_conc_now}) reached",
            )
        pos = paper_store.add_position(
            underlying=sym,
            sized_trade=best_sized,
            entry_spot_price=spot_price,
            notes=body.notes,
            is_paper=_is_paper_mode(),
            trail_mode_name=mode.name if mode else None,
            trail_atr_mult=mode.trail_atr_mult if mode else 2.0,
            initial_sl=_initial_sl,
            initial_tp=_initial_tp,
            exit_mode="two_red",  # unification with kite exit counter
        )
    return pos


@router.post("/monitor-all")
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

    # (helper defined at module level above for reuse)

    async def _monitor_one(pos: PaperPosition) -> Optional[MonitorResult]:
        async with _sem:
            try:
                inst = registry.get_instrument(pos.underlying)
                if not inst:
                    return None
                adapter = _live_adapter
                c1h = await adapter.get_candles(inst, "1H", limit=400)
                signal = compute_signal(c1h)

                current_spot = await adapter.get_index_price(inst)

                # DTE and P&L are computed BEFORE any exit path can return. They used to
                # be initialised to 0.0/0 here and only filled in after the red-count
                # check, which meant two things at once: the red path closed the position
                # while reporting `estimated_pnl_usd` of exactly 0.00 and `current_dte` 0
                # — a fabricated number on a real exit — and the "record first" snapshot
                # below was in fact unreachable for that path, despite saying otherwise.
                leg = pos.sized_trade.structure.legs[0] if pos.sized_trade.structure.legs else None
                dte_from_expiry = _dte_from_expiry(leg.expiry_date) if leg else -1
                if dte_from_expiry >= 0:
                    current_dte = dte_from_expiry
                else:
                    days_elapsed = int((now_ms - pos.entry_timestamp_ms) / 86_400_000)
                    current_dte = max(0, (leg.dte if leg else 0) - days_elapsed)
                spot_move      = current_spot - pos.entry_spot_price
                direction_sign = 1 if pos.sized_trade.structure.direction.value == "long" else -1
                estimated_pnl  = _estimate_pnl(
                    pos.sized_trade, spot_move, direction_sign,
                    pos.sized_trade.max_risk_usd,
                    pos.sized_trade.structure.max_gain,
                )

                # Now genuinely first: every exit path below is preceded by this.
                pnl_history.record(pos.id, current_spot, estimated_pnl, current_dte, now_ms)

                red_result = _compute_red_and_maybe_close(
                    pos, signal, current_spot, now_ms, estimated_pnl, current_dte
                )
                if red_result:
                    return red_result

                # ── Trail update (mirrors monitor_position logic) ─────────────
                if pos.trail_stop_json and pos.status.value in ("open", "partially_closed"):
                    try:
                        from app.engines.directional.trailing_stop import TrailState, TrailingStopEngine
                        from app.core.trading_mode import MODES, DEFAULT_MODE
                        _ts  = TrailState.from_json(pos.trail_stop_json)
                        _mo  = getattr(request.app.state, "trading_mode", None) or MODES[DEFAULT_MODE]
                        _dir = "bullish" if direction_sign == 1 else "bearish"
                        _st  = signal.st_values[0] if signal.st_values else 0.0
                        _tu  = TrailingStopEngine().update(
                            state=_ts, candles=c1h[-30:], st_value=_st,
                            direction=_dir,
                            entry_price=pos.entry_price_real or pos.entry_spot_price,
                            mode=_mo, initial_tp=pos.initial_tp,
                        )
                        _new_sl = round(_tu.new_stop, 4)
                        paper_store.update_position(
                            pos.id,
                            trail_stop_json=_ts.to_json(),
                            current_sl=_new_sl,
                            current_tp=pos.current_tp,
                        )
                        if _tu.stopped_out:
                            paper_store.close_position(pos.id, float(current_spot))
                            return MonitorResult(
                                position_id=pos.id, underlying=pos.underlying,
                                exit_signal=ExitSignal(
                                    should_exit=True,
                                    reason=f"Trail stop hit at {_new_sl:.2f}",
                                    exit_type="trail_stop",
                                ),
                                current_spot=current_spot, estimated_pnl_usd=estimated_pnl,
                                current_dte=current_dte, current_signal_trend=signal.trend,
                                timestamp_ms=now_ms,
                            )
                        if _tu.partial and pos.status == PositionStatus.OPEN:
                            _pr = getattr(_tu.partial, "partial_ratio", 0.25)
                            _pp = paper_store.partial_close_position(pos.id, float(current_spot), _pr)
                            if _pp:
                                _p_cal = getattr(request.app.state, "calibration_service", None)
                                if _p_cal:
                                    _slice = (_pp.realized_pnl_usd or 0.0) - (pos.realized_pnl_usd or 0.0)
                                    _p_cal.record_trade(_slice / max(pos.sized_trade.max_risk_usd * _pr, 1.0), "unknown")
                    except Exception:
                        pass

                exit_signal = check_exits(
                    pos.sized_trade, signal, estimated_pnl, current_dte,
                    current_spot=float(current_spot),
                    current_tp=pos.current_tp,
                    current_sl=pos.current_sl,
                    force_exit_dte=inst.force_exit_dte,
                    financial_stop_pct=risk.financial_stop_pct,
                    partial_profit_r1=risk.partial_profit_r1,
                    partial_profit_r2=risk.partial_profit_r2,
                )

                # Auto-execute: full exit → close position
                if exit_signal.should_exit and not exit_signal.partial:
                    paper_store.close_position(pos.id, float(current_spot))
                # Auto-execute: partial → reduce contracts, book P&L
                elif exit_signal.partial and pos.status == PositionStatus.OPEN:
                    _pr2 = getattr(exit_signal, "partial_ratio", 0.50)
                    paper_store.partial_close_position(pos.id, float(current_spot), _pr2)

                return MonitorResult(
                    position_id=pos.id, underlying=pos.underlying,
                    exit_signal=exit_signal, current_spot=current_spot,
                    estimated_pnl_usd=estimated_pnl, current_dte=current_dte,
                    current_signal_trend=signal.trend, timestamp_ms=now_ms,
                )
            except Exception as exc:  # noqa: BLE001
                # Never kill the whole sweep for one position — but never swallow it
                # silently either. This returned None on any failure, so `monitor-all`
                # reported `open_positions_checked=N` while having actually monitored
                # none of them: no P&L snapshot, no trail update, no exit check, and
                # nothing anywhere saying so.
                log.warning("monitor-all: %s (%s) could not be monitored: %s",
                            pos.id, pos.underlying, exc, exc_info=True)
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

@router.get("/{pos_id}/trail-stop")
async def get_trail_stop(pos_id: str) -> dict:
    """Return current trailing stop state for a position."""
    pos = paper_store.get_position(pos_id.upper())
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {pos_id} not found")
    raw = getattr(pos, "trail_stop_json", None)
    if not raw:
        return {
            "stop": None, "mode": None, "highest_seen": None,
            "partial_25_done": False, "partial_50_done": False,
            "stop_moved_last_check": False,
        }
    try:
        from app.engines.directional.trailing_stop import TrailState
        state = TrailState.from_json(raw)
        return {
            "stop": state.current_stop,
            "mode": state.mode.value,
            "highest_seen": state.highest_seen,
            "partial_25_done": state.partial_25_done,
            "partial_50_done": state.partial_50_done,
            "stop_moved_last_check": False,
        }
    except Exception:
        return {"stop": None, "mode": None, "highest_seen": None,
                "partial_25_done": False, "partial_50_done": False,
                "stop_moved_last_check": False}


@router.get("/{pos_id}/pnl-history")
async def get_pnl_history(pos_id: str):
    """Session P&L snapshots for a position — recorded on each monitor call."""
    snapshots = pnl_history.get_history(pos_id.upper())
    return {
        "position_id": pos_id.upper(),
        "snapshots": [s.model_dump() for s in snapshots],
        "count": len(snapshots),
    }


@router.patch("/{pos_id}/notes")
async def update_position_notes(pos_id: str, notes: str = "") -> PaperPosition:
    """Update trade journal notes for a paper position."""
    pos = paper_store.update_position(pos_id.upper(), notes=notes)
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {pos_id} not found")
    return pos


@router.get("/{pos_id}")
async def get_position(pos_id: str) -> PaperPosition:
    pos = paper_store.get_position(pos_id.upper())
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {pos_id} not found")
    return pos


@router.post("/{pos_id}/close")
async def close_position(pos_id: str, body: ClosePositionRequest, request: Request) -> PaperPosition:
    pos = paper_store.get_position(pos_id.upper())
    updated = paper_store.close_position(pos_id.upper(), body.exit_spot_price, body.notes)
    if not updated:
        raise HTTPException(
            status_code=404, detail=f"Position {pos_id} not found or already closed"
        )
    # Record calibration trade on close — use max_risk_usd as denominator so pnl_pct
    # is a return-on-risk ratio (correct input for fractional Kelly win_rate estimation).
    if pos and updated.realized_pnl_usd is not None:
        svc = getattr(request.app.state, 'calibration_service', None)
        if svc:
            max_risk = pos.sized_trade.max_risk_usd if pos.sized_trade else 0.0
            pnl_pct = updated.realized_pnl_usd / max(max_risk, 1.0)
            regime = getattr(pos, 'regime', 'unknown') or 'unknown'
            svc.record_trade(float(pnl_pct), str(regime))
        # Record equity snapshot
        from app.services import db as _db
        all_pos = paper_store.list_positions()
        open_pos = [p for p in all_pos if p.status.value in ('open', 'partially_closed')]
        pv = sum(p.sized_trade.max_risk_usd for p in open_pos) + sum(
            p.realized_pnl_usd for p in all_pos
            if p.status.value == 'closed' and p.realized_pnl_usd
        )
        dd_breaker = getattr(request.app.state, 'dd_circuit_breaker', None)
        cb_state = dd_breaker.state.value if dd_breaker else None
        _db.record_equity_snapshot(pv, cb_state=cb_state)
    return updated


@router.post("/{pos_id}/monitor")
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
        c1h = await adapter.get_candles(inst, "1H", limit=400)
        signal = compute_signal(c1h)
        current_spot = await adapter.get_index_price(inst)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {exc}") from exc

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
        current_spot=float(current_spot),
        current_tp=pos.current_tp,
        current_sl=pos.current_sl,
        force_exit_dte=inst.force_exit_dte,
        financial_stop_pct=risk.financial_stop_pct,
        partial_profit_r1=risk.partial_profit_r1,
        partial_profit_r2=risk.partial_profit_r2,
    )

    # Record P&L snapshot for session history
    pnl_history.record(pos.id, current_spot, estimated_pnl, current_dte, now_ms)

    # Update trailing stop state
    if pos.trail_stop_json and pos.status.value in ("open", "partially_closed"):
        try:
            from app.engines.directional.trailing_stop import TrailState, TrailingStopEngine
            from app.core.trading_mode import MODES, DEFAULT_MODE
            trail_state = TrailState.from_json(pos.trail_stop_json)
            mode_obj = getattr(request.app.state, "trading_mode", None) or MODES[DEFAULT_MODE]
            direction_str = "bullish" if direction_sign == 1 else "bearish"
            st_val = signal.st_values[0] if signal.st_values else 0.0
            trail_update = TrailingStopEngine().update(
                state=trail_state,
                candles=c1h[-30:],
                st_value=st_val,
                direction=direction_str,
                entry_price=pos.entry_price_real or pos.entry_spot_price,
                mode=mode_obj,
                initial_tp=pos.initial_tp,
            )
            # Persist updated trail state and live SL/TP
            _new_sl = round(trail_update.new_stop, 4)

            # B3: trailing TP — re-evaluate using the same 1H candles + ATR.
            # Skips silently if guards (entry/spot side, threshold) prevent update.
            _new_tp = pos.current_tp
            try:
                if _new_tp is not None and pos.current_sl is not None:
                    from app.engines.directional.dynamic_tp import recompute_tp as _recompute_tp
                    import numpy as _np_local
                    _highs = _np_local.array([_c.high for _c in c1h], dtype=_np_local.float64)
                    _lows  = _np_local.array([_c.low  for _c in c1h], dtype=_np_local.float64)
                    _closes_local = _np_local.array([_c.close for _c in c1h], dtype=_np_local.float64)
                    from app.engines.indicators.atr import compute_atr as _compute_atr_local
                    _atr_arr = _compute_atr_local(_highs, _lows, _closes_local, 14)
                    _atr_now = float(_atr_arr[-1]) if len(_atr_arr) > 0 else 0.0
                    _entry_p = pos.entry_price_real or pos.entry_spot_price
                    _sl_dist = abs(_entry_p - pos.current_sl)
                    _rr_target = mode_obj.rr_target if mode_obj else 2.0
                    _candidate_tp, _changed, _src = _recompute_tp(
                        direction="long" if direction_sign == 1 else "short",
                        entry=_entry_p,
                        current_tp=_new_tp,
                        current_spot=float(current_spot),
                        stop_dist=_sl_dist,
                        rr=_rr_target,
                        highs=_highs, lows=_lows, atr=_atr_now,
                    )
                    if _changed:
                        _new_tp = _candidate_tp
            except Exception:
                pass

            paper_store.update_position(
                pos.id,
                trail_stop_json=trail_state.to_json(),
                current_sl=_new_sl,
                current_tp=_new_tp,
            )
            # Telegram notifications
            from app.services.notifications import telegram as _tg
            from app.services.notifications.formatters import fmt_trail_update, fmt_partial_exit, fmt_position_closed
            if trail_update.stop_moved:
                gain_pct = (float(current_spot) - (pos.entry_price_real or pos.entry_spot_price)) / max(pos.entry_price_real or pos.entry_spot_price, 1)
                await _tg.send(fmt_trail_update(pos, trail_update.new_stop, gain_pct))
            if trail_update.partial:
                await _tg.send(fmt_partial_exit(pos, trail_update.partial))
            if trail_update.stopped_out and not exit_signal.should_exit:
                paper_store.close_position(pos.id, float(current_spot))
                await _tg.send(fmt_position_closed(pos, estimated_pnl, "Trail stop hit"))
        except Exception:
            pass

    # Auto-execute: full exit → close position
    if exit_signal.should_exit and not exit_signal.partial:
        paper_store.close_position(pos.id, float(current_spot))
    # Auto-execute: partial → reduce contracts, book partial P&L, record calibration
    elif exit_signal.partial and pos.status == PositionStatus.OPEN:
        _partial_ratio = getattr(exit_signal, "partial_ratio", 0.50) or 0.50
        _partial_pos   = paper_store.partial_close_position(
            pos.id, float(current_spot), _partial_ratio
        )
        if _partial_pos and _partial_pos.realized_pnl_usd is not None:
            _p_cal = getattr(request.app.state, "calibration_service", None)
            if _p_cal:
                _prev_r    = pos.realized_pnl_usd or 0.0
                _slice_pnl = _partial_pos.realized_pnl_usd - _prev_r
                _risk_sl   = pos.sized_trade.max_risk_usd * _partial_ratio
                _p_pct     = _slice_pnl / max(_risk_sl, 1.0)
                _p_regime  = getattr(pos, "regime", "unknown") or "unknown"
                _p_cal.record_trade(float(_p_pct), str(_p_regime))

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
