"""Monte Carlo robustness on a trade sequence.

A single backtest equity curve is ONE realization of a random process — its
final return and max drawdown are point estimates. Resampling the trade
sequence (reorder = path/sequence risk; bootstrap = sampling risk) produces a
distribution, so we can report confidence bands instead of a single number
('the −27% max DD you saw could plausibly be −40%').
"""
from __future__ import annotations

import numpy as np

from app.engines.analytics.monte_carlo import monte_carlo_trades, MonteCarloResult


def test_deterministic_with_seed():
    rets = [0.05, -0.03, 0.02, -0.01, 0.04, -0.02]
    a = monte_carlo_trades(rets, n_sims=500, seed=42)
    b = monte_carlo_trades(rets, n_sims=500, seed=42)
    assert a.return_pct_p50 == b.return_pct_p50
    assert a.max_dd_pct_p95 == b.max_dd_pct_p95


def test_all_winners_never_lose():
    rets = [0.01] * 50
    r = monte_carlo_trades(rets, n_sims=300, seed=1, method="bootstrap")
    assert r.prob_loss == 0.0
    assert r.return_pct_p05 > 0          # even the 5th percentile is profitable
    assert r.max_dd_pct_p50 == 0.0       # monotonic up → no drawdown


def test_percentiles_ordered():
    rng = np.random.default_rng(0)
    rets = list(rng.normal(0.001, 0.02, 200))
    r = monte_carlo_trades(rets, n_sims=1000, seed=7)
    assert r.return_pct_p05 <= r.return_pct_p50 <= r.return_pct_p95
    # max DD is reported as a negative pct; p05 is the WORST (most negative)
    assert r.max_dd_pct_p05 <= r.max_dd_pct_p50 <= r.max_dd_pct_p95 <= 0.0


def test_reorder_preserves_final_return():
    """Reordering the SAME trades multiplicatively → identical final return on
    every path (only the drawdown path changes). That isolates sequence risk."""
    rets = [0.05, -0.03, 0.02, -0.04, 0.06]
    r = monte_carlo_trades(rets, n_sims=200, seed=3, method="reorder")
    assert abs(r.return_pct_p05 - r.return_pct_p95) < 1e-9    # all equal
    # but drawdown varies across orderings
    assert r.max_dd_pct_p05 <= r.max_dd_pct_p95


def test_bootstrap_widens_return_band():
    """Bootstrap (sample with replacement) must produce a WIDER return spread
    than reorder (which fixes the multiset)."""
    rng = np.random.default_rng(1)
    rets = list(rng.normal(0.002, 0.03, 150))
    reo = monte_carlo_trades(rets, n_sims=1000, seed=5, method="reorder")
    boo = monte_carlo_trades(rets, n_sims=1000, seed=5, method="bootstrap")
    reo_spread = reo.return_pct_p95 - reo.return_pct_p05
    boo_spread = boo.return_pct_p95 - boo.return_pct_p05
    assert boo_spread > reo_spread


def test_empty_returns_safe():
    r = monte_carlo_trades([], n_sims=100, seed=0)
    assert isinstance(r, MonteCarloResult)
    assert r.n_trades == 0 and r.prob_loss == 0.0
