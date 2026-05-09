"""
Walk-forward, sensitivity, and performance analytics endpoints.
"""
import json
import time
from dataclasses import asdict
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional

from app.engines.analytics.walk_forward import WalkForwardConfig, run as wf_run, WalkForwardResult
from app.engines.analytics.sensitivity import run_all_sweeps, SWEEP_PARAMS
from app.engines.analytics.performance import full_report
from app.services import db as _db

router = APIRouter(prefix="/analytics", tags=["analytics"])


class WalkForwardRequest(BaseModel):
    underlying: str = "BTC"
    train_bars: int = 180
    test_bars: int = 60
    step_bars: int = 30


class SensitivityRequest(BaseModel):
    underlying: str = "BTC"
    params: Optional[list] = None  # subset of SWEEP_PARAMS keys, or None=all


def _candles_to_dicts(candles) -> list:
    """Convert candle objects to dicts with 'close' key."""
    result = []
    for c in candles:
        if hasattr(c, 'close'):
            result.append({'close': float(c.close), 'regime': 'unknown'})
        elif isinstance(c, dict):
            result.append({'close': float(c.get('close', 0)), 'regime': c.get('regime', 'unknown')})
    return result


def _wf_result_to_dict(result: WalkForwardResult) -> dict:
    """Serialize WalkForwardResult to JSON-compatible dict."""
    def report_dict(r):
        return {
            'sharpe': r.sharpe,
            'calmar': r.calmar,
            'sortino': r.sortino,
            'max_drawdown': r.max_drawdown,
            'win_rate': r.win_rate,
            'avg_rr': r.avg_rr,
            'profit_factor': r.profit_factor,
            'total_trades': r.total_trades,
            'regime_breakdown': r.regime_breakdown,
        }

    return {
        'windows': [
            {
                'window_idx': w.window_idx,
                'train_start': w.train_start,
                'test_start': w.test_start,
                'test_end': w.test_end,
                'report': report_dict(w.report),
                'best_threshold': w.best_threshold,
                'equity_curve': w.equity_curve,
            }
            for w in result.windows
        ],
        'aggregate_report': report_dict(result.aggregate_report),
        'recommended_threshold': result.recommended_threshold,
        'regime_sharpes': result.regime_sharpes,
        'oos_equity_curve': result.oos_equity_curve,
    }


@router.post("/walk-forward")
async def run_walk_forward(
    body: WalkForwardRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict:
    """Run walk-forward backtest. Fetches candles from active adapter."""
    from app.services import adapter_manager as _adm
    from app.services.exchanges import instrument_registry as registry

    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    adapter = _adm.get_adapter() or request.app.state.adapter
    try:
        candles_4h = await adapter.get_candles(inst, "4H", limit=body.train_bars + body.test_bars + 50)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}")

    candle_dicts = _candles_to_dicts(candles_4h)
    config = WalkForwardConfig(
        train_bars=body.train_bars,
        test_bars=body.test_bars,
        step_bars=body.step_bars,
        underlying=sym,
    )

    try:
        result = wf_run(candle_dicts, config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Walk-forward failed: {exc}")

    result_dict = _wf_result_to_dict(result)
    config_json = json.dumps({'train_bars': body.train_bars, 'test_bars': body.test_bars, 'step_bars': body.step_bars})
    oos_sharpe = result.aggregate_report.sharpe

    background_tasks.add_task(
        _db.save_wf_result,
        sym, config_json, json.dumps(result_dict), result.recommended_threshold, oos_sharpe,
    )

    return {**result_dict, 'underlying': sym, 'timestamp_ms': int(time.time() * 1000)}


@router.get("/walk-forward/{underlying}/latest")
async def get_latest_wf(underlying: str) -> dict:
    """Return most recent walk-forward result from DB."""
    row = _db.get_latest_wf_result(underlying.upper())
    if not row:
        raise HTTPException(status_code=404, detail=f"No walk-forward results for {underlying}")
    result_data = json.loads(row['result_json'])
    return {
        **result_data,
        'underlying': underlying.upper(),
        'run_at': row['run_at'],
        'recommended_threshold': row['recommended_threshold'],
        'oos_sharpe': row['oos_sharpe'],
    }


@router.post("/sensitivity")
async def run_sensitivity(
    body: SensitivityRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> list:
    """Run parameter sensitivity sweep."""
    from app.services import adapter_manager as _adm
    from app.services.exchanges import instrument_registry as registry

    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    adapter = _adm.get_adapter() or request.app.state.adapter
    try:
        candles_4h = await adapter.get_candles(inst, "4H", limit=300)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}")

    candle_dicts = _candles_to_dicts(candles_4h)
    base_config = {'score_min': 72}

    try:
        if body.params:
            from app.engines.analytics.sensitivity import sweep
            results = []
            for p in body.params:
                if p in SWEEP_PARAMS:
                    r = sweep(candle_dicts, p, SWEEP_PARAMS[p], base_config)
                    results.append({
                        'parameter': r.parameter,
                        'values_tested': r.values_tested,
                        'sharpes': r.sharpes,
                        'best_value': r.best_value,
                        'sensitivity': r.sensitivity,
                    })
        else:
            results_raw = run_all_sweeps(candle_dicts, base_config)
            results = [
                {
                    'parameter': r.parameter,
                    'values_tested': r.values_tested,
                    'sharpes': r.sharpes,
                    'best_value': r.best_value,
                    'sensitivity': r.sensitivity,
                }
                for r in results_raw
            ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sensitivity sweep failed: {exc}")

    background_tasks.add_task(
        _db.save_sensitivity, sym, json.dumps(results)
    )
    return results


@router.get("/sensitivity/{underlying}/latest")
async def get_latest_sensitivity(underlying: str) -> dict:
    """Return cached sensitivity results."""
    import datetime
    row = _db.get_latest_sensitivity(underlying.upper())
    if not row:
        raise HTTPException(status_code=404, detail=f"No sensitivity results for {underlying}")
    computed_at = row.get('computed_at', '')
    stale_days = 0
    if computed_at:
        try:
            dt = datetime.datetime.fromisoformat(str(computed_at))
            stale_days = (datetime.datetime.utcnow() - dt).days
        except Exception:
            pass
    return {
        'underlying': underlying.upper(),
        'results': json.loads(row['results_json']),
        'computed_at': computed_at,
        'stale_days': stale_days,
        'is_stale': stale_days > 7,
    }


@router.get("/performance/{underlying}")
async def get_performance(underlying: str) -> dict:
    """PerformanceReport from all closed positions for this underlying."""
    import numpy as np
    sym = underlying.upper()
    closed = _db.get_closed_positions_for(sym)
    trades = _closed_to_trades(closed, sym)
    snapshots = _db.get_equity_snapshots(limit=1000)
    equity_curve = _build_equity_curve(snapshots)

    if len(trades) < 2:
        return {'underlying': sym, 'message': 'Insufficient data', 'total_trades': len(trades)}

    report = full_report(equity_curve, trades)
    return {
        'underlying': sym,
        'sharpe': report.sharpe,
        'calmar': report.calmar,
        'sortino': report.sortino,
        'max_drawdown': report.max_drawdown,
        'win_rate': report.win_rate,
        'avg_rr': report.avg_rr,
        'profit_factor': report.profit_factor,
        'total_trades': report.total_trades,
        'regime_breakdown': report.regime_breakdown,
    }


@router.get("/performance/portfolio")
async def get_portfolio_performance() -> dict:
    """Aggregate PerformanceReport across all underlyings."""
    closed = _db.get_closed_positions_for()
    trades = _closed_to_trades(closed)
    snapshots = _db.get_equity_snapshots(limit=1000)
    equity_curve = _build_equity_curve(snapshots)

    if len(trades) < 2:
        return {'message': 'Insufficient data', 'total_trades': len(trades)}

    report = full_report(equity_curve, trades)
    return {
        'sharpe': report.sharpe,
        'calmar': report.calmar,
        'sortino': report.sortino,
        'max_drawdown': report.max_drawdown,
        'win_rate': report.win_rate,
        'avg_rr': report.avg_rr,
        'profit_factor': report.profit_factor,
        'total_trades': report.total_trades,
        'regime_breakdown': report.regime_breakdown,
    }


def _closed_to_trades(closed_positions: list, underlying: str | None = None) -> list:
    """Convert closed position dicts to trade format for performance.full_report."""
    trades = []
    for pos in closed_positions:
        pnl = pos.get('realized_pnl_usd', 0.0) or 0.0
        entry_spot = pos.get('entry_spot_price', 1.0) or 1.0
        pnl_pct = pnl / max(entry_spot, 1.0) / 100  # rough approximation
        regime = pos.get('regime', 'unknown') or 'unknown'
        trades.append({'pnl_pct': float(pnl_pct), 'regime': str(regime)})
    return trades


def _build_equity_curve(snapshots: list) -> 'np.ndarray':
    import numpy as np
    if not snapshots:
        return np.array([1.0, 1.0])
    vals = [s.get('portfolio_value', 1.0) for s in reversed(snapshots) if s.get('portfolio_value')]
    if len(vals) < 2:
        return np.array([1.0, 1.0])
    base = vals[0]
    return np.array([v / base for v in vals])
