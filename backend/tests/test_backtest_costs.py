"""
Phase 1 truthful-costs tests.

Covers compute_trade_costs (unit) and the next-bar-open execution model
used by the MTF engine.
"""
import pytest

from app.engines.backtest.costs import (
    compute_trade_costs,
    next_bar_open_fill,
)
from app.schemas.market import Candle


# ── fixtures ──────────────────────────────────────────────────────────────────

def _candle(ts_ms: int, o: float, c: float | None = None) -> Candle:
    c = c if c is not None else o
    return Candle(
        timestamp_ms=ts_ms, open=o, high=max(o, c) * 1.001,
        low=min(o, c) * 0.999, close=c, volume=100.0,
    )


# ── slippage worsens fills ────────────────────────────────────────────────────

def test_long_slippage_worsens_entry_and_exit():
    bd = compute_trade_costs(
        direction=+1, entry_price=100.0, exit_price=110.0,
        leverage=10, oi=None, fee_rt_pct=0.0,
    )
    assert bd.effective_entry_price > bd.entry_price
    assert bd.effective_exit_price  < bd.exit_price
    assert bd.slippage_pct > 0


def test_short_slippage_worsens_entry_and_exit():
    bd = compute_trade_costs(
        direction=-1, entry_price=100.0, exit_price=90.0,
        leverage=10, oi=None, fee_rt_pct=0.0,
    )
    # short: enter by selling (worse = lower), exit by buying (worse = higher)
    assert bd.effective_entry_price < bd.entry_price
    assert bd.effective_exit_price  > bd.exit_price
    assert bd.slippage_pct > 0


def test_apply_slippage_false_zeroes_slippage():
    bd = compute_trade_costs(
        direction=+1, entry_price=100.0, exit_price=101.0,
        leverage=10, apply_slippage=False, fee_rt_pct=0.0,
    )
    assert bd.slippage_bps == 0.0
    assert bd.slippage_pct == 0.0
    assert bd.effective_entry_price == pytest.approx(100.0)
    assert bd.effective_exit_price  == pytest.approx(101.0)


# ── funding ───────────────────────────────────────────────────────────────────

def test_funding_cost_8h_and_16h():
    """Funding cost must scale linearly with actual holding time."""
    rate = 0.0002  # 2 bps / 8h
    bd_8 = compute_trade_costs(
        direction=+1, entry_price=100.0, exit_price=100.0,
        hold_hours=8.0, funding_8h_pct=rate,
        fee_rt_pct=0.0, apply_slippage=False,
    )
    bd_16 = compute_trade_costs(
        direction=+1, entry_price=100.0, exit_price=100.0,
        hold_hours=16.0, funding_8h_pct=rate,
        fee_rt_pct=0.0, apply_slippage=False,
    )
    assert bd_8.funding_pct  == pytest.approx(rate)
    assert bd_16.funding_pct == pytest.approx(2 * rate)


def test_funding_signed_by_direction():
    """Positive funding rate drags longs and credits shorts."""
    long_bd = compute_trade_costs(
        direction=+1, entry_price=100.0, exit_price=100.0,
        hold_hours=8.0, funding_8h_pct=0.0001,
        fee_rt_pct=0.0, apply_slippage=False,
    )
    short_bd = compute_trade_costs(
        direction=-1, entry_price=100.0, exit_price=100.0,
        hold_hours=8.0, funding_8h_pct=0.0001,
        fee_rt_pct=0.0, apply_slippage=False,
    )
    assert long_bd.funding_pct  > 0   # cost for long
    assert short_bd.funding_pct < 0   # credit for short


# ── option spread ─────────────────────────────────────────────────────────────

def test_option_half_spread_cost_when_quotes_exist():
    bd = compute_trade_costs(
        direction=+1, entry_price=100.0, exit_price=100.0,
        option_spread_pct=0.005,
        fee_rt_pct=0.0, apply_slippage=False,
    )
    assert bd.option_spread_pct == pytest.approx(0.005)
    assert bd.total_cost_pct    == pytest.approx(0.005)


def test_missing_quote_data_produces_zero_spread_cost():
    """option_spread_pct=None must not crash and must produce zero spread cost."""
    bd = compute_trade_costs(
        direction=+1, entry_price=100.0, exit_price=100.0,
        option_spread_pct=None,
        fee_rt_pct=0.0, apply_slippage=False,
    )
    assert bd.option_spread_pct == 0.0
    assert bd.total_cost_pct    == pytest.approx(0.0)


# ── cost attribution invariant ────────────────────────────────────────────────

def test_cost_total_equals_sum_of_components():
    bd = compute_trade_costs(
        direction=+1, entry_price=100.0, exit_price=110.0,
        leverage=10, oi=500.0,                        # slippage band: medium
        fee_rt_pct=0.001,
        hold_hours=8.0, funding_8h_pct=0.0001,
        option_spread_pct=0.002,
    )
    components = (
        bd.slippage_pct + bd.fee_pct
        + bd.funding_pct + bd.option_spread_pct
    )
    assert bd.total_cost_pct == pytest.approx(components, abs=1e-12)
    assert bd.net_pnl_pct == pytest.approx(
        bd.gross_pnl_pct - bd.total_cost_pct, abs=1e-12,
    )


def test_gross_pnl_is_directional():
    """Long: pnl positive when exit > entry; short: positive when exit < entry."""
    long_up = compute_trade_costs(
        direction=+1, entry_price=100.0, exit_price=105.0,
        fee_rt_pct=0.0, apply_slippage=False,
    )
    short_down = compute_trade_costs(
        direction=-1, entry_price=100.0, exit_price=95.0,
        fee_rt_pct=0.0, apply_slippage=False,
    )
    assert long_up.gross_pnl_pct    > 0
    assert short_down.gross_pnl_pct > 0


# ── next-bar-open fill helper ─────────────────────────────────────────────────

def test_next_bar_open_fill_returns_next_open():
    candles = [
        _candle(0,            100.0, 101.0),
        _candle(60_000,       102.0, 103.0),
        _candle(120_000,      104.0, 105.0),
    ]
    fill = next_bar_open_fill(candles, signal_idx=0)
    assert fill is not None
    price, bar_idx = fill
    assert price == 102.0    # open of candles[1]
    assert bar_idx == 1


def test_next_bar_open_fill_none_on_last_bar():
    """No future bar → None → caller must skip / explicitly mark forced_end."""
    candles = [_candle(0, 100.0), _candle(60_000, 101.0)]
    assert next_bar_open_fill(candles, signal_idx=1) is None
    assert next_bar_open_fill(candles, signal_idx=99) is None


def test_negative_or_zero_entry_price_raises():
    with pytest.raises(ValueError):
        compute_trade_costs(
            direction=+1, entry_price=0.0, exit_price=100.0,
        )
