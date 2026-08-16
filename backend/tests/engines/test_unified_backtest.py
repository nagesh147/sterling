"""
Unit tests for the Unified Institutional Multi-Strategy Backtesting Engine.
"""

import math
import pytest
import pandas as pd
import numpy as np

from app.schemas.backtest import UnifiedBacktestRequest, UnifiedBacktestResult
from app.engines.backtest.unified_engine import (
    run_unified_backtest,
    generate_strategy_signals,
    calculate_atr,
    calculate_supertrend,
    calculate_rsi,
    calculate_bollinger_bands,
)


@pytest.fixture
def sample_real_candles():
    """Generates 150 realistic 5-minute OHLCV candles."""
    np.random.seed(42)
    n = 150
    timestamps = pd.date_range("2026-05-01 09:15:00", periods=n, freq="5min")
    price = 24500.0
    candles = []
    for i in range(n):
        ret = np.random.normal(0.0002, 0.0015)
        price = price * (1.0 + ret)
        o = price + np.random.uniform(-5, 5)
        h = max(o, price) + abs(np.random.normal(0, 10))
        l = min(o, price) - abs(np.random.normal(0, 10))
        c = price
        v = float(np.random.randint(1000, 10000))
        candles.append({
            "timestamp": timestamps[i].isoformat(),
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": v,
        })
    return candles


def test_indicator_calculations(sample_real_candles):
    df = pd.DataFrame(sample_real_candles)
    df["open"] = pd.to_numeric(df["open"])
    df["high"] = pd.to_numeric(df["high"])
    df["low"] = pd.to_numeric(df["low"])
    df["close"] = pd.to_numeric(df["close"])

    atr = calculate_atr(df, 14)
    assert len(atr) == len(df)
    assert not atr.iloc[-1] == 0.0

    st_trend, st_line = calculate_supertrend(df, 10, 3.0)
    assert len(st_trend) == len(df)
    assert len(st_line) == len(df)
    assert st_trend.dtype == bool

    rsi = calculate_rsi(df["close"], 14)
    assert len(rsi) == len(df)
    assert 0 <= rsi.iloc[-1] <= 100

    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(df["close"], 20, 2.0)
    assert len(bb_upper) == len(df)
    assert (bb_upper >= bb_lower).all()


@pytest.mark.parametrize("strategy", [
    "adaptive_edge",
    "supertrend",
    "navigator",
    "directional",
    "mean_reversion",
])
def test_all_strategies_generate_signals(strategy, sample_real_candles):
    df = pd.DataFrame(sample_real_candles)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col])

    longs, shorts = generate_strategy_signals(df, strategy, {})
    assert len(longs) == len(df)
    assert len(shorts) == len(df)
    assert longs.dtype == bool
    assert shorts.dtype == bool


def test_unified_backtest_execution_adaptive_edge(sample_real_candles):
    req = UnifiedBacktestRequest(
        strategy="adaptive_edge",
        symbol="NIFTY 50",
        timeframe="5m",
        lookback_days=10,
        starting_capital=100000.0,
        lot_size=25,
        num_lots=2,
        slippage_points=0.5,
        brokerage_per_order=20.0,
        stt_pct=0.00125,
        stop_points=40.0,
        target_points=80.0,
        trail_points=25.0,
    )

    result = run_unified_backtest(sample_real_candles, req)
    assert isinstance(result, UnifiedBacktestResult)
    assert result.strategy == "adaptive_edge"
    assert result.symbol == "NIFTY 50"
    assert result.candles_evaluated == len(sample_real_candles)
    assert len(result.equity_curve) == len(sample_real_candles)
    assert result.starting_capital == 100000.0

    # Friction is strictly deducted
    metrics = result.metrics
    assert metrics.total_friction_inr >= 0.0
    if len(result.trades) > 0:
        t = result.trades[0]
        assert t.gross_pnl != 0.0
        assert t.friction_cost > 0.0
        assert t.net_pnl == round(t.gross_pnl - t.friction_cost, 2)
        assert t.exit_reason in ["TARGET", "STOP_LOSS", "TRAILING_STOP", "SESSION_CUTOFF", "SIGNAL_REVERSAL", "MANUAL_EXIT"]


def test_unified_backtest_insufficient_candles():
    req = UnifiedBacktestRequest(strategy="supertrend", symbol="NIFTY 50")
    with pytest.raises(ValueError, match="Insufficient candle history"):
        run_unified_backtest([], req)


def test_monte_carlo_resampling_on_sufficient_trades(sample_real_candles):
    # Force frequent entries with small stop/target
    req = UnifiedBacktestRequest(
        strategy="mean_reversion",
        symbol="NIFTY 50",
        timeframe="5m",
        lookback_days=10,
        starting_capital=100000.0,
        stop_points=10.0,
        target_points=15.0,
    )
    result = run_unified_backtest(sample_real_candles, req)
    if len(result.trades) >= 5:
        assert result.monte_carlo is not None
        assert result.monte_carlo.simulations == 500
        assert isinstance(result.monte_carlo.mean_return_pct, float)
        assert 0.0 <= result.monte_carlo.prob_profit_pct <= 100.0
