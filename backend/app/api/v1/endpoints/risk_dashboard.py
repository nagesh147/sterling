"""
Risk dashboard: correlation, Greeks budget, drawdown circuit breaker, calibration, slippage.
"""
import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/correlation")
async def get_correlation(request: Request) -> dict:
    """Cross-asset correlation matrix."""
    tracker = getattr(request.app.state, 'correlation_tracker', None)
    if tracker is None:
        return {'matrix': {}, 'assets': [], 'updated_at': int(time.time() * 1000)}
    try:
        mat = tracker.matrix()
        matrix_serializable = {f"{a}:{b}": round(v, 4) for (a, b), v in mat.items()}
        return {
            'matrix': matrix_serializable,
            'assets': tracker.assets,
            'updated_at': int(time.time() * 1000),
        }
    except Exception as exc:
        return {'matrix': {}, 'assets': [], 'error': str(exc), 'updated_at': int(time.time() * 1000)}


@router.get("/greeks")
async def get_greeks_budget(request: Request) -> dict:
    """Portfolio Greeks vs budget."""
    budget_checker = getattr(request.app.state, 'greeks_budget_checker', None)
    from app.services import paper_store
    from app.engines.risk.greeks_budget import GreeksBudget

    open_pos = [p for p in paper_store.list_positions() if p.status.value in ('open', 'partially_closed')]

    budget = GreeksBudget()
    net_delta = net_vega = net_theta = 0.0

    for pos in open_pos:
        greeks_json = getattr(pos, 'greeks_json', None)
        notional = getattr(pos, 'notional', None) or pos.sized_trade.max_risk_usd
        if greeks_json:
            import json
            g = json.loads(greeks_json)
            net_delta += g.get('delta', 0.0) * notional
            net_vega  += g.get('vega', 0.0) * notional
            net_theta += g.get('theta', 0.0) * notional

    pv = sum(p.sized_trade.max_risk_usd for p in open_pos) or 1.0
    return {
        'net_delta': round(net_delta / pv, 4),
        'net_vega': round(net_vega / pv, 4),
        'net_theta': round(net_theta / pv, 4),
        'budget': {
            'max_net_delta': budget.max_net_delta,
            'max_net_vega': budget.max_net_vega,
            'max_net_theta': budget.max_net_theta,
        },
        'within_limits': (
            abs(net_delta / pv) <= budget.max_net_delta and
            abs(net_vega / pv) <= budget.max_net_vega and
            net_theta / pv >= budget.max_net_theta
        ),
        'open_positions': len(open_pos),
        'timestamp_ms': int(time.time() * 1000),
    }


@router.get("/circuit-breaker")
async def get_circuit_breaker(request: Request) -> dict:
    """Drawdown circuit breaker state."""
    breaker = getattr(request.app.state, 'dd_circuit_breaker', None)
    if breaker is None:
        return {
            'state': 'clear',
            'current_drawdown': 0.0,
            'peak_value': 0.0,
            'current_value': 0.0,
            'thresholds': {'warn': 0.05, 'halt': 0.10, 'reset': 0.15},
            'size_multiplier': 1.0,
        }

    from app.services import paper_store
    from app.services import db as _db

    snapshots = _db.get_equity_snapshots(limit=1)
    current_value = snapshots[0]['portfolio_value'] if snapshots else breaker.peak

    return {
        'state': breaker.state.value,
        'current_drawdown': round(breaker.current_drawdown(current_value), 4),
        'peak_value': round(breaker.peak, 2),
        'current_value': round(current_value, 2),
        'thresholds': {
            'warn': breaker.cfg.warn_dd,
            'halt': breaker.cfg.halt_dd,
            'reset': breaker.cfg.reset_dd,
        },
        'size_multiplier': breaker.size_multiplier(),
        'timestamp_ms': int(time.time() * 1000),
    }


class ResetConfirm(BaseModel):
    confirm: bool = False


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(body: ResetConfirm, request: Request) -> dict:
    """Manual reset of drawdown circuit breaker."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Must confirm: {confirm: true}")
    breaker = getattr(request.app.state, 'dd_circuit_breaker', None)
    if breaker is None:
        raise HTTPException(status_code=503, detail="Circuit breaker not initialised")
    breaker.reset()
    return {'state': 'clear', 'message': 'Circuit breaker reset successfully'}


@router.get("/calibration/{underlying}")
async def get_calibration(underlying: str, request: Request) -> dict:
    """Adaptive calibration state: win_rate, IVR bands."""
    svc = getattr(request.app.state, 'calibration_service', None)
    if svc is None:
        return {
            'underlying': underlying.upper(),
            'win_rate': 0.52,
            'ivr_buy_threshold': 30.0,
            'ivr_sell_threshold': 70.0,
            'trade_count': 0,
            'ivr_readings': 0,
        }
    sym = underlying.upper()
    buy_thr, sell_thr = svc.ivr_bands(sym)
    wr = svc.win_rate()  # None on cold start
    return {
        'underlying': sym,
        'win_rate': round(wr, 4) if wr is not None else None,
        'cold_start': wr is None,
        'ivr_buy_threshold': round(buy_thr, 2),
        'ivr_sell_threshold': round(sell_thr, 2),
        'trade_count': svc.trade_count(),
        'ivr_readings': svc.ivr_readings_count(sym),
        'note': 'Requires >=10 trades for regime-specific rates, >=20 IVR readings for adaptive bands.',
    }


@router.get("/slippage-estimate")
async def get_slippage_estimate(leverage: float = 10.0, oi: Optional[float] = None) -> dict:
    """Estimate slippage for given leverage and OI."""
    from app.engines.risk.slippage import slippage_bps, effective_entry, size_after_slippage
    bps = slippage_bps(leverage, oi)
    size_factor = size_after_slippage(1.0, leverage, oi)
    adj_long = effective_entry(100.0, 1, leverage, oi) - 100.0
    return {
        'leverage': leverage,
        'oi': oi,
        'bps': bps,
        'effective_entry_adjustment_pct': round(adj_long, 4),
        'size_reduction_factor': round(size_factor, 4),
    }
