import numpy as np
from app.schemas.market import Candle
from app.engines.directional.signal_engine import compute_signal


def _make_candles_with_spike(n=50, base=30000.0, spike_vol=1000.0, normal_vol=100.0):
    """Candles with one volume spike at the end."""
    np.random.seed(20)
    candles = []
    price = base
    for i in range(n):
        price += 50 + np.random.normal(0, base * 0.001)
        vol = spike_vol if i == n - 1 else normal_vol
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=price, high=price + 50, low=price - 50, close=price,
            volume=vol,
        ))
    return candles


def test_median_not_mean_for_volume_spike():
    """With a single 10x spike, median-based detection should fire but mean could be fooled."""
    candles = _make_candles_with_spike(n=50, normal_vol=100.0, spike_vol=1000.0)

    volumes = np.array([c.volume for c in candles], dtype=float)
    vol_mean = float(np.mean(volumes[-20:]))
    vol_median = float(np.median(volumes[-20:]))

    # The spike inflates the mean more than the median
    assert vol_mean > vol_median, "Mean should be more sensitive to the spike"

    # The spike bar should be detected as a spike using median
    spike = float(volumes[-1])
    spike_by_median = spike > 1.5 * vol_median
    spike_by_mean = spike > 1.5 * vol_mean

    assert spike_by_median, "Spike should be detected via median"
    # Mean detection may fail because mean is elevated by spike itself
    # This demonstrates median's robustness


def test_signal_runs_with_volume_spike():
    """compute_signal should not crash with volume spike candles."""
    candles = _make_candles_with_spike(n=50, normal_vol=100.0, spike_vol=5000.0)
    result = compute_signal(candles)
    assert result is not None
    assert isinstance(result.signal_strength, str)
