"""
Tests for T1: Truthful Backtest Costs (Tier S) additions.
Covers leg-by-leg options spread cost, dynamic fee cost model,
default funding drag, and symmetric slippage.
"""
import pytest
from app.engines.backtest.costs import (
    compute_trade_costs,
    make_cost_model,
    next_bar_open_fill,
)
from app.schemas.market import Candle
from app.engines.backtest.backtest_mtf import run_mtf_backtest, TFProfile


def _candle(ts_ms: int, o: float, c: float | None = None) -> Candle:
    c = c if c is not None else o
    return Candle(
        timestamp_ms=ts_ms, open=o, high=max(o, c) * 1.001,
        low=min(o, c) * 0.999, close=c, volume=100.0,
    )


def test_make_cost_model():
    # Spreads should have 0.20% RT fee
    assert make_cost_model("bull_call_spread") == pytest.approx(0.002)
    assert make_cost_model("bear_put_spread") == pytest.approx(0.002)
    assert make_cost_model("spread") == pytest.approx(0.002)

    # Futures and Naked options should have 0.10% RT fee
    assert make_cost_model("futures") == pytest.approx(0.001)
    assert make_cost_model("naked_call") == pytest.approx(0.001)
    assert make_cost_model("naked_put") == pytest.approx(0.001)
    assert make_cost_model("") == pytest.approx(0.001)


def test_option_legs_spread_cost():
    legs = [
        {"ask": 105.0, "bid": 95.0, "mid": 100.0},  # (105-95)/(2*100) = 10/200 = 0.05
        {"ask": 52.0, "bid": 48.0, "mid_price": 50.0},  # (52-48)/(2*50) = 4/100 = 0.04
    ]
    bd = compute_trade_costs(
        direction=1,
        entry_price=100.0,
        exit_price=110.0,
        structure_type="spread",
        option_legs=legs,
        fee_rt_pct=0.0,
        apply_slippage=False,
    )
    # Expected option_spread_pct = 0.05 + 0.04 = 0.09
    assert bd.option_spread_pct == pytest.approx(0.09)
    assert bd.total_cost_pct == pytest.approx(0.09)
    # gross = 10%
    # net = 10% - 9% = 1%
    assert bd.gross_pnl_pct == pytest.approx(0.10)
    assert bd.net_pnl_pct == pytest.approx(0.01)


def test_default_funding_drag_for_futures():
    # 8 hours hold with default funding drag should be exactly 0.01% (0.0001)
    bd_futures = compute_trade_costs(
        direction=1,
        entry_price=100.0,
        exit_price=100.0,
        structure_type="futures",
        hold_hours=8.0,
        fee_rt_pct=0.0,
        apply_slippage=False,
    )
    assert bd_futures.funding_pct == pytest.approx(0.0001)

    # 16 hours hold should be 0.0002
    bd_futures_16h = compute_trade_costs(
        direction=1,
        entry_price=100.0,
        exit_price=100.0,
        structure_type="futures",
        hold_hours=16.0,
        fee_rt_pct=0.0,
        apply_slippage=False,
    )
    assert bd_futures_16h.funding_pct == pytest.approx(0.0002)

    # Non-futures should NOT have default funding drag
    bd_options = compute_trade_costs(
        direction=1,
        entry_price=100.0,
        exit_price=100.0,
        structure_type="spread",
        hold_hours=8.0,
        fee_rt_pct=0.0,
        apply_slippage=False,
    )
    assert bd_options.funding_pct == pytest.approx(0.0)


def test_effective_entry_slippage():
    # Symmetrical slippage validation:
    # Long: effective entry price should be higher than clean entry, exit lower than clean exit.
    bd_long = compute_trade_costs(
        direction=1,
        entry_price=100.0,
        exit_price=100.0,
        leverage=10.0,
        oi=1.5,
        fee_rt_pct=0.0,
        apply_slippage=True,
    )
    assert bd_long.effective_entry_price > 100.0
    assert bd_long.effective_exit_price < 100.0

    # Short: effective entry price should be lower than clean entry, exit higher than clean exit.
    bd_short = compute_trade_costs(
        direction=-1,
        entry_price=100.0,
        exit_price=100.0,
        leverage=10.0,
        oi=1.5,
        fee_rt_pct=0.0,
        apply_slippage=True,
    )
    assert bd_short.effective_entry_price < 100.0
    assert bd_short.effective_exit_price > 100.0


def test_run_mtf_backtest_with_cost_model():
    # Simple integration test ensuring run_mtf_backtest uses the cost model fees
    # Scalping profile needs 15M/1H. Let's make minimal candles.
    c15 = [_candle(ts, 100.0) for ts in range(0, 40 * 15 * 60000, 15 * 60000)]
    c1h = [_candle(ts, 100.0) for ts in range(0, 40 * 60 * 60000, 60 * 60000)]
    c4h = [_candle(ts, 100.0) for ts in range(0, 40 * 4 * 60 * 60000, 4 * 60 * 60000)]

    # Run for spreads (which should resolve fee_rt_pct to 0.002)
    res_spread = run_mtf_backtest(
        "BTC",
        candles_15m=c15,
        candles_1h=c1h,
        candles_4h=c4h,
        profiles=["scalping_15m"],
        structure_type="bull_call_spread",
        apply_slippage=False,
    )
    # Check that fee RT rate was used
    # (Since there are no signals/trades in flat candles, we just verify it runs and doesn't crash)
    assert "scalping_15m" in res_spread
