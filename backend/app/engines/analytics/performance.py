"""
Unified performance metrics.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PerformanceReport:
    sharpe:          float
    calmar:          float
    sortino:         float
    max_drawdown:    float
    win_rate:        float
    avg_rr:          float
    profit_factor:   float
    total_trades:    int
    regime_breakdown: dict = field(default_factory=dict)


def sharpe(equity_curve: np.ndarray, periods_per_year: int = 8760) -> float:
    """Hourly bars default. Annualised Sharpe, rf=0."""
    rets = np.diff(equity_curve) / equity_curve[:-1]
    if rets.std() == 0:
        return 0.0
    return float(np.mean(rets) / rets.std() * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity_curve)
    dd = (equity_curve - peak) / peak
    return float(np.min(dd))


def calmar(equity_curve: np.ndarray, periods_per_year: int = 8760) -> float:
    rets = np.diff(equity_curve) / equity_curve[:-1]
    ann_ret = np.mean(rets) * periods_per_year
    mdd = abs(max_drawdown(equity_curve))
    return float(ann_ret / mdd) if mdd > 0 else 0.0


def sortino(equity_curve: np.ndarray, periods_per_year: int = 8760) -> float:
    rets = np.diff(equity_curve) / equity_curve[:-1]
    neg = rets[rets < 0]
    downside_std = max(float(np.std(neg)), 1e-9) if len(neg) > 0 else 1e-9
    return float(np.mean(rets) / downside_std * np.sqrt(periods_per_year))


def regime_breakdown(trades: list) -> dict:
    """Group trades by regime, compute Sharpe proxy and win_rate per group."""
    from collections import defaultdict
    groups = defaultdict(list)
    for t in trades:
        groups[t.get('regime', 'unknown')].append(t['pnl_pct'])
    out = {}
    for regime, pnls in groups.items():
        arr = np.array(pnls)
        out[regime] = {
            'trade_count': len(arr),
            'win_rate': float(np.mean(arr > 0)),
            'avg_pnl': float(np.mean(arr)),
            'sharpe_proxy': float(np.mean(arr) / arr.std()) if arr.std() > 0 else 0.0,
        }
    return out


def full_report(equity_curve: np.ndarray, trades: list) -> PerformanceReport:
    pnls = [t['pnl_pct'] for t in trades]
    winners = [p for p in pnls if p > 0]
    losers  = [p for p in pnls if p < 0]
    return PerformanceReport(
        sharpe        = sharpe(equity_curve),
        calmar        = calmar(equity_curve),
        sortino       = sortino(equity_curve),
        max_drawdown  = max_drawdown(equity_curve),
        win_rate      = len(winners) / len(pnls) if pnls else 0.0,
        avg_rr        = (np.mean(winners) / abs(np.mean(losers))) if losers else 0.0,
        profit_factor = (sum(winners) / abs(sum(losers))) if losers else 0.0,
        total_trades  = len(trades),
        regime_breakdown = regime_breakdown(trades),
    )
