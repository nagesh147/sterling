import numpy as np
import pytest
from app.engines.analytics.performance import sharpe, max_drawdown, calmar, sortino, full_report, regime_breakdown


def test_sharpe_flat_returns():
    curve = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    assert sharpe(curve) == 0.0


def test_max_drawdown_monotonic_up():
    curve = np.array([1.0, 1.1, 1.2, 1.3, 1.4])
    assert max_drawdown(curve) == pytest.approx(0.0, abs=1e-9)


def test_max_drawdown_50pct():
    curve = np.array([1.0, 0.5])
    assert max_drawdown(curve) == pytest.approx(-0.5, abs=1e-9)


def test_calmar_positive():
    curve = np.array([1.0, 1.05, 1.10, 1.08, 1.15])
    assert calmar(curve) > 0


def test_regime_breakdown_keys():
    trades = [
        {'pnl_pct': 0.02, 'regime': 'BULL_TREND'},
        {'pnl_pct': -0.01, 'regime': 'BEAR_TREND'},
        {'pnl_pct': 0.01, 'regime': 'VOLATILE'},
        {'pnl_pct': 0.00, 'regime': 'NEUTRAL'},
    ]
    result = regime_breakdown(trades)
    assert 'BULL_TREND' in result
    assert 'BEAR_TREND' in result
    assert 'VOLATILE' in result
    assert 'NEUTRAL' in result


def test_full_report_win_rate():
    trades = [
        {'pnl_pct': 0.05, 'regime': 'BULL'},
        {'pnl_pct': 0.03, 'regime': 'BULL'},
        {'pnl_pct': 0.02, 'regime': 'BULL'},
        {'pnl_pct': 0.01, 'regime': 'BULL'},
        {'pnl_pct': 0.04, 'regime': 'BULL'},
        {'pnl_pct': 0.06, 'regime': 'BULL'},
        {'pnl_pct': 0.07, 'regime': 'BULL'},
        {'pnl_pct': -0.02, 'regime': 'BULL'},
        {'pnl_pct': -0.03, 'regime': 'BULL'},
        {'pnl_pct': -0.01, 'regime': 'BULL'},
    ]
    curve = np.array([1.0] + [1.0] * len(trades))
    v = 1.0
    for i, t in enumerate(trades):
        v *= (1 + t['pnl_pct'])
        curve[i + 1] = v
    report = full_report(curve, trades)
    assert report.win_rate == pytest.approx(0.7, abs=0.01)
    assert report.total_trades == 10
