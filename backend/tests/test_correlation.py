import pytest
from app.engines.analytics.correlation import CorrelationTracker


def _tracker_with_corr(corr: float) -> CorrelationTracker:
    """Create a tracker where BTC and ETH have approximately `corr` correlation."""
    import numpy as np
    tracker = CorrelationTracker(assets=['BTC', 'ETH'])
    # Feed perfectly correlated or uncorrelated returns
    rng = np.random.default_rng(42)
    base = rng.normal(0, 0.01, 100)
    noise = rng.normal(0, 0.01, 100)
    btc_prices = np.cumprod(1 + base) * 1000
    if corr >= 0.99:
        eth_prices = np.cumprod(1 + base) * 500
    else:
        eth_prices = np.cumprod(1 + noise) * 500
    for b, e in zip(btc_prices, eth_prices):
        tracker.update('BTC', float(b))
        tracker.update('ETH', float(e))
    return tracker


def test_perfect_correlation_penalty():
    tracker = _tracker_with_corr(1.0)
    penalty = tracker.portfolio_correlation_penalty('BTC', ['ETH'])
    assert penalty == pytest.approx(0.4, abs=0.05)


def test_uncorrelated_no_penalty():
    tracker = _tracker_with_corr(0.0)
    penalty = tracker.portfolio_correlation_penalty('BTC', ['ETH'])
    assert penalty in (1.0, 0.7)  # low corr → no penalty or low penalty


def test_no_open_positions_no_penalty():
    tracker = CorrelationTracker(assets=['BTC', 'ETH'])
    penalty = tracker.portfolio_correlation_penalty('BTC', [])
    assert penalty == pytest.approx(1.0)
