"""
DSR scaling regression tests.

The deflated Sharpe ratio in `edge/robustness.py` previously compared a
*per-trade* Sharpe (~0.2) against the expected max of N *standard normals*
(~2.9) by multiplying their difference by sqrt(t-1) — scaling the benchmark
along with the observation. That saturated DSR to ~0 for every config,
including configs that genuinely beat buy-and-hold, making the gate
uninformative.

The fix converts the observed Sharpe to standard-error (t-stat) units FIRST,
then deflates by the expected max under the null. These tests pin that the
gate now discriminates: strong edges clear a modest deflation hurdle, the
hurdle tightens with more trials, stronger edges score higher, and pure noise
is still rejected.
"""
from app.engines.edge.robustness import deflated_sharpe_ratio


def _stream(n_pos: int, pos: float, n_neg: int, neg: float) -> list[float]:
    """Deterministic per-trade return stream: n_pos winners then n_neg losers."""
    return [pos] * n_pos + [neg] * n_neg


# A genuine edge: 60 winners of +4%, 40 losers of -2% over 100 trades.
# mean ~+1.6%, std ~2.94% -> per-trade Sharpe ~0.54 (t-stat ~5.4 over 100).
STRONG = _stream(60, 0.04, 40, -0.02)
# A marginal edge: 55 winners / 45 losers of equal magnitude -> Sharpe ~0.1.
WEAK = _stream(55, 0.02, 45, -0.02)
# Zero edge: balanced wins/losses -> Sharpe ~0.
NOISE = _stream(50, 0.02, 50, -0.02)


def test_strong_edge_clears_modest_deflation():
    # With only 10 trials of multiple-testing, a Sharpe-~0.54 stream over 100
    # trades should be clearly significant. The buggy version returned ~0.
    dsr = deflated_sharpe_ratio(STRONG, num_trials=10)
    assert dsr > 0.5, f"strong edge should survive modest deflation, got {dsr}"


def test_more_trials_tighten_the_hurdle():
    # More strategies tried -> harder to clear -> lower DSR. The buggy version
    # returned 0.0 for both, so the strict inequality failed.
    few = deflated_sharpe_ratio(STRONG, num_trials=2)
    many = deflated_sharpe_ratio(STRONG, num_trials=1000)
    assert few > many, f"expected DSR to fall as trials rise, got {few} -> {many}"


def test_stronger_edge_scores_higher_than_weaker():
    # Same trial count and sample size; only the edge differs.
    strong = deflated_sharpe_ratio(STRONG, num_trials=10)
    weak = deflated_sharpe_ratio(WEAK, num_trials=10)
    assert strong > weak, f"stronger edge should score higher, got {strong} vs {weak}"


def test_pure_noise_is_rejected():
    # A zero-Sharpe stream must not clear the gate even at the easiest hurdle.
    dsr = deflated_sharpe_ratio(NOISE, num_trials=2)
    assert dsr < 0.5, f"zero-edge noise should be rejected, got {dsr}"


def test_too_few_trades_returns_zero():
    # Contract unchanged: not enough samples -> no claim of significance.
    assert deflated_sharpe_ratio([0.05] * 5, num_trials=2) == 0.0
