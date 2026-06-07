"""Buy-and-hold benchmark for backtests.

A strategy result is only meaningful relative to passively holding the same
asset over the same window. The edge study never computed this, so a long-only
momentum strategy that returned +95% in a market that tripled looked like
"edge" when it was actually *worse than HODL*. These tests pin the benchmark
and the gate that encodes "you only beat buy-and-hold if you made MORE money
AND took LESS drawdown".
"""
from __future__ import annotations

from app.engines.analytics.performance import hodl_benchmark, beats_buy_and_hold


def test_net_return_is_price_appreciation_minus_round_trip_fee():
    # +21% gross over the window, one 0.1% round-trip fee.
    h = hodl_benchmark([100.0, 110.0, 121.0], fee_rt_pct=0.001)
    assert abs(h["net_return"] - (0.21 - 0.001)) < 1e-9


def test_max_drawdown_is_worst_peak_to_trough_on_the_price_path():
    # equity path normalises to [1.0, 1.2, 0.6, 0.9]; worst DD = (0.6-1.2)/1.2.
    h = hodl_benchmark([100.0, 120.0, 60.0, 90.0])
    assert abs(h["max_drawdown"] - (-0.5)) < 1e-9


def test_monotonic_up_market_has_zero_drawdown():
    h = hodl_benchmark([100.0, 150.0, 200.0])
    assert h["max_drawdown"] == 0.0
    assert abs(h["net_return"] - 1.0) < 1e-9


def test_degenerate_inputs_do_not_raise():
    for bad in ([], [100.0], [0.0, 100.0]):
        h = hodl_benchmark(bad)
        assert h["net_return"] == 0.0
        assert h["max_drawdown"] == 0.0


def test_a_strategy_that_returns_less_than_hold_does_not_beat_it():
    # The central audit finding: +95% strategy vs a market that doubled.
    h = hodl_benchmark([100.0, 200.0])              # +100%, zero drawdown
    b = beats_buy_and_hold(strategy_net_return=0.95,
                           strategy_max_dd=-0.272, hodl=h)
    assert b["beats_hold_return"] is False
    assert b["beats_hold"] is False
    assert abs(b["excess_return"] - (0.95 - 1.0)) < 1e-9


def test_beating_hold_requires_both_more_return_and_less_drawdown():
    # HODL: +150% but a 50% drawdown along the way.
    h = hodl_benchmark([100.0, 50.0, 250.0])
    assert abs(h["net_return"] - 1.5) < 1e-9
    assert abs(h["max_drawdown"] - (-0.5)) < 1e-9

    # More return AND shallower drawdown -> genuinely beats hold.
    good = beats_buy_and_hold(1.6, -0.10, h)
    assert good["beats_hold"] is True

    # More return but DEEPER drawdown -> does not beat (risk-adjusted).
    risky = beats_buy_and_hold(1.6, -0.70, h)
    assert risky["beats_hold_return"] is True
    assert risky["beats_hold_dd"] is False
    assert risky["beats_hold"] is False
