"""
Black-Scholes pricing unit tests.
All values cross-checked against known BSM references.
"""
import math
import pytest

from app.engines.backtest.bs_pricing import (
    bs_price, bs_delta, bs_gamma, bs_vega, bs_theta,
    atm_option_pnl_pct,
)


# ATM call: spot=strike=100, T=30d, IV=80%, r=0
# d1 = (0 + 0.5*0.64*30/365) / (0.8*sqrt(30/365)) ≈ 0.148
# Expected: ~7.2
def test_bs_atm_call_price_range():
    # spot=strike=100, T=30/365, IV=80% → d1≈0.115, call≈9.1
    p = bs_price(100.0, 100.0, 30, 0.80, "call")
    assert p is not None
    assert 8.0 < p < 11.0, f"ATM call price out of expected range: {p}"


def test_bs_atm_put_price_range():
    p = bs_price(100.0, 100.0, 30, 0.80, "put")
    assert p is not None
    assert 8.0 < p < 11.0, f"ATM put price out of expected range: {p}"


def test_put_call_parity():
    """C - P = S - K*e^(-rT)  for same strike."""
    s, k, dte, iv = 100.0, 100.0, 30, 0.80
    c = bs_price(s, k, dte, iv, "call")
    p = bs_price(s, k, dte, iv, "put")
    assert c is not None and p is not None
    # ATM: C - P ≈ 0 (spot ≈ PV of strike at r=0)
    assert abs(c - p) < 0.01, f"Put-call parity violated: C={c}, P={p}"


def test_deep_itm_call_price():
    """Deep ITM call should be close to intrinsic value (spot - strike)."""
    p = bs_price(200.0, 100.0, 30, 0.80, "call")
    assert p is not None
    assert p > 99.0  # intrinsic = 100, time value small


def test_deep_otm_call_price():
    """Deep OTM call should have near-zero value."""
    p = bs_price(50.0, 200.0, 30, 0.80, "call")
    assert p is not None
    assert p < 0.01


def test_bs_invalid_inputs_return_none():
    assert bs_price(0, 100, 30, 0.8, "call") is None      # zero spot
    assert bs_price(100, 0, 30, 0.8, "call") is None      # zero strike
    assert bs_price(100, 100, 0, 0.8, "call") is None     # zero dte
    assert bs_price(100, 100, 30, 0.0, "call") is None    # zero iv


def test_call_delta_range():
    d = bs_delta(100.0, 100.0, 30, 0.80, "call")
    assert 0.4 < d < 0.6, f"ATM call delta should be ~0.5, got {d}"


def test_put_delta_range():
    d = bs_delta(100.0, 100.0, 30, 0.80, "put")
    assert -0.6 < d < -0.4, f"ATM put delta should be ~-0.5, got {d}"


def test_delta_put_call_relationship():
    """delta_call - delta_put = 1 for same strike."""
    dc = bs_delta(100.0, 100.0, 30, 0.80, "call")
    dp = bs_delta(100.0, 100.0, 30, 0.80, "put")
    assert abs(dc - dp - 1.0) < 0.001


def test_gamma_positive():
    g = bs_gamma(100.0, 100.0, 30, 0.80)
    assert g > 0


def test_vega_positive():
    v = bs_vega(100.0, 100.0, 30, 0.80)
    assert v > 0


def test_theta_negative():
    """Time decay should be negative (value erodes over time)."""
    t = bs_theta(100.0, 100.0, 30, 0.80, "call")
    assert t < 0, f"Theta should be negative, got {t}"


def test_atm_option_pnl_pct_call_spot_up():
    """Spot up 5% on a call should be profitable."""
    pnl = atm_option_pnl_pct(
        spot_entry=50_000.0, spot_exit=52_500.0,
        dte_entry=30, dte_exit=26,
        iv=0.80, option_type="call",
    )
    assert pnl is not None and pnl > 0, f"Expected profit on call with rising spot, got {pnl}"


def test_atm_option_pnl_pct_call_spot_down():
    """Spot down 5% on a call should be a loss."""
    pnl = atm_option_pnl_pct(
        spot_entry=50_000.0, spot_exit=47_500.0,
        dte_entry=30, dte_exit=26,
        iv=0.80, option_type="call",
    )
    assert pnl is not None and pnl < 0, f"Expected loss on call with falling spot, got {pnl}"


def test_atm_option_pnl_pct_put_spot_down():
    """Spot down 5% on a put should be profitable."""
    pnl = atm_option_pnl_pct(
        spot_entry=50_000.0, spot_exit=47_500.0,
        dte_entry=30, dte_exit=26,
        iv=0.80, option_type="put",
    )
    assert pnl is not None and pnl > 0, f"Expected profit on put with falling spot, got {pnl}"


def test_atm_option_pnl_at_expiry_otm_is_total_loss():
    """OTM at expiry → full premium lost (-100%)."""
    pnl = atm_option_pnl_pct(
        spot_entry=50_000.0, spot_exit=48_000.0,   # spot < strike → call OTM
        dte_entry=30, dte_exit=0,
        iv=0.80, option_type="call",
    )
    assert pnl is not None and pnl < -90.0, f"OTM at expiry should be near -100%, got {pnl}"


def test_backtest_engine_with_bs(tmp_path):
    """End-to-end: run_backtest produces bs_entry_premium when atm_iv supplied."""
    import os
    os.environ["STERLING_DB_PATH"] = ":memory:"

    from app.schemas.market import Candle
    from app.engines.backtest.backtest_engine import run_backtest

    # Build 500 synthetic 1H candles (random walk)
    base = 50_000.0
    candles_1h = []
    for i in range(500):
        c = base * (1 + 0.001 * ((i % 7) - 3))
        candles_1h.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=c, high=c * 1.001, low=c * 0.999, close=c, volume=100.0,
        ))
        base = c

    candles_4h = candles_1h[::4]

    result = run_backtest(
        underlying="BTC",
        candles_4h=candles_4h,
        candles_1h=candles_1h,
        lookback_days=14,
        sample_every_n_bars=4,
        atm_iv=0.80,
        option_dte=30,
    )

    assert result.atm_iv_used == 0.80
    assert result.option_dte_used == 30
    # At least some bars should have BS fields populated
    bars_with_bs = [b for b in result.bars if b.bs_entry_premium is not None]
    assert len(bars_with_bs) > 0, "Expected some bars with BS pricing"
    for b in bars_with_bs:
        assert b.bs_entry_premium > 0

    # Without atm_iv: bs fields should be absent
    result_no_bs = run_backtest(
        underlying="BTC",
        candles_4h=candles_4h,
        candles_1h=candles_1h,
        lookback_days=14,
        sample_every_n_bars=4,
    )
    assert result_no_bs.atm_iv_used is None
    bars_with_bs_none = [b for b in result_no_bs.bars if b.bs_entry_premium is not None]
    assert len(bars_with_bs_none) == 0
