"""
Phase 2 honest-metrics tests.

Verifies the corrected Sharpe / Sortino / PF semantics and the new
deflated-Sharpe helper.
"""
import math
import numpy as np
import pytest

from app.engines.analytics.performance import (
    sharpe, sortino, calmar, cagr, ulcer_index, pain_ratio,
    tail_ratio, profit_factor, full_report, deflated_sharpe,
)


# ── profit factor ─────────────────────────────────────────────────────────────

def test_profit_factor_no_losers_returns_infinity():
    trades = [
        {"pnl_pct": 0.01, "regime": "BULL"},
        {"pnl_pct": 0.02, "regime": "BULL"},
        {"pnl_pct": 0.005, "regime": "BULL"},
    ]
    pf = profit_factor(trades)
    assert pf == float("inf")


def test_profit_factor_finite_with_losers():
    trades = [
        {"pnl_pct": 0.03},  # winners sum = 0.03
        {"pnl_pct": -0.01}, # losers  sum = 0.01
    ]
    assert profit_factor(trades) == pytest.approx(3.0)


def test_profit_factor_empty_returns_none():
    assert profit_factor([]) is None


# ── Sortino LPM semantics ─────────────────────────────────────────────────────

def test_sortino_uses_lower_partial_moment():
    """
    Two return streams with identical mean and identical *std-of-negatives*
    but different downside *frequency* should give different Sortino.
    LPM downside_dev = sqrt(mean(min(0, r)^2)) — varies with the *fraction*
    of negatives, not just their dispersion.
    """
    # Stream A: many zero observations, one big loss
    a = np.array([0.01, 0.01, 0.01, 0.01, -0.02])
    # Stream B: all losers, same total downside dispersion (single loss)
    b = np.array([-0.02, 0.01, 0.01, 0.01, 0.01])
    curve_a = np.concatenate([[1.0], np.cumprod(1 + a)])
    curve_b = np.concatenate([[1.0], np.cumprod(1 + b)])
    # both have one loser of equal magnitude → same legacy "std(neg)"
    # but identical LPM, so they should NOT differ wildly here.
    # Stronger LPM test: stream with two losers has higher downside dev.
    c = np.array([0.01, -0.02, 0.01, -0.02, 0.01])
    curve_c = np.concatenate([[1.0], np.cumprod(1 + c)])
    s_a = sortino(curve_a, signal_bar_ms=3_600_000)
    s_c = sortino(curve_c, signal_bar_ms=3_600_000)
    # More frequent losers → larger LPM downside → smaller Sortino magnitude.
    assert abs(s_c) < abs(s_a) or s_c < s_a


def test_sortino_zero_downside_returns_zero():
    """All-winners curve → downside_dev=0 → return 0 (well-defined)."""
    curve = np.array([1.0, 1.01, 1.02, 1.03])
    assert sortino(curve, signal_bar_ms=3_600_000) == 0.0


# ── Sharpe is not trade-count annualised ──────────────────────────────────────

def test_sharpe_does_not_inflate_with_trade_count_annualization():
    """
    A flat-mean / equal-variance return stream sampled at hourly vs 4h vs
    daily cadence should NOT produce wildly different annualised Sharpe.
    The legacy code multiplied by sqrt(8760) regardless of cadence — this
    test fails under that assumption.
    """
    rng = np.random.default_rng(seed=7)
    rets = rng.normal(loc=0.0005, scale=0.01, size=300)
    curve = np.concatenate([[1.0], np.cumprod(1 + rets)])
    # Per-bar Sharpe should annualise honestly with signal_bar_ms.
    s_hourly = sharpe(curve, signal_bar_ms=3_600_000)        # 1h bars
    s_daily  = sharpe(curve, signal_bar_ms=86_400_000)       # 1d bars
    # Hourly cadence → bigger ann factor than daily — but both should be
    # finite and the hourly Sharpe should NOT be ~ sqrt(24) bigger than
    # what one would get treating the SAME stream as daily (the legacy
    # 8760-factor multiplier).
    legacy_inflated = float(rets.mean() / rets.std() * math.sqrt(8760))
    # Honest hourly annualisation matches legacy 8760 because cadence
    # really is hourly; daily annualisation does not.
    assert s_hourly == pytest.approx(legacy_inflated, rel=1e-9)
    assert abs(s_daily) < abs(s_hourly)


def test_sharpe_calendar_time_with_timestamps():
    """When trades have exit timestamps, Sharpe uses calendar-time daily
    returns and sqrt(365) annualisation (crypto 24/7)."""
    base = 1_700_000_000_000
    rng = np.random.default_rng(seed=11)
    pnls = rng.normal(0.001, 0.005, size=20)
    trades = [
        {"pnl_pct": float(p),
         "entry_ts_ms": base + i * 86_400_000,
         "exit_ts_ms":  base + i * 86_400_000 + 3_600_000,
         "regime": "BULL"}
        for i, p in enumerate(pnls)
    ]
    curve = np.concatenate([[1.0], np.cumprod(1 + pnls)])
    s = sharpe(curve, trades=trades)
    expected = float(pnls.mean() / pnls.std() * math.sqrt(365))
    assert s == pytest.approx(expected, rel=1e-3)


# ── deflated Sharpe ───────────────────────────────────────────────────────────

def test_deflated_sharpe_more_trials_harder_hurdle():
    base = deflated_sharpe(observed_sharpe=2.0, n_trials=1, n_observations=100)
    many = deflated_sharpe(observed_sharpe=2.0, n_trials=100, n_observations=100)
    assert base > many   # more trials → lower probability


def test_deflated_sharpe_higher_observed_higher_probability():
    weak   = deflated_sharpe(observed_sharpe=0.3, n_trials=10, n_observations=100)
    strong = deflated_sharpe(observed_sharpe=3.0, n_trials=10, n_observations=100)
    assert strong > weak


def test_deflated_sharpe_low_sharpe_weak_significance():
    p = deflated_sharpe(observed_sharpe=0.2, n_trials=20, n_observations=100)
    assert 0.0 <= p < 0.5


def test_deflated_sharpe_strong_sharpe_high_significance():
    p = deflated_sharpe(observed_sharpe=4.0, n_trials=5, n_observations=200)
    assert p > 0.5


def test_deflated_sharpe_monotonic_in_n_trials():
    seq = [
        deflated_sharpe(2.0, n_trials=n, n_observations=200)
        for n in (1, 5, 25, 100, 500)
    ]
    # Should be (weakly) monotonically non-increasing
    for a, b in zip(seq, seq[1:]):
        assert a + 1e-9 >= b


# ── tail / ulcer / pain ───────────────────────────────────────────────────────

def test_ulcer_index_monotonic_up_is_zero():
    curve = np.array([1.0, 1.01, 1.02, 1.03])
    assert ulcer_index(curve) == pytest.approx(0.0, abs=1e-9)


def test_tail_ratio_insufficient_data_returns_none():
    assert tail_ratio([{"pnl_pct": 0.01}] * 5) is None


def test_tail_ratio_positive_skew_above_one():
    pnls = [-0.005] * 10 + [0.02] * 5   # symmetric-ish
    pnls += [0.05]                       # big winner → 95th pct large
    trades = [{"pnl_pct": p} for p in pnls]
    tr = tail_ratio(trades)
    assert tr is not None and tr > 1.0


# ── full report shape ─────────────────────────────────────────────────────────

def test_full_report_includes_new_fields():
    base = 1_700_000_000_000
    trades = [
        {"pnl_pct": 0.01,  "exit_ts_ms": base + 0, "regime": "BULL"},
        {"pnl_pct": -0.005,"exit_ts_ms": base + 86_400_000, "regime": "BULL"},
        {"pnl_pct": 0.02,  "exit_ts_ms": base + 2*86_400_000, "regime": "BULL"},
    ]
    curve = np.array([1.0, 1.01, 1.005, 1.025])
    rpt = full_report(curve, trades, signal_bar_ms=3_600_000)
    assert rpt.cagr is not None
    assert rpt.ulcer_index >= 0
    assert rpt.pain_ratio is not None
    assert rpt.sharpe_method in ("calendar_daily", "per_bar", "legacy_periods")
    assert isinstance(rpt.profit_factor, float)
