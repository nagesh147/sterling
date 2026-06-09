"""Regime book — classifier, short sleeves, router, portfolio sim, walk-forward."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from study.regime_book import classify_regime


def _frame(closes, atr=None):
    closes = np.asarray(closes, float)
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="4h")
    high = closes * 1.005
    low = closes * 0.995
    df = pd.DataFrame({"open": closes, "high": high, "low": low,
                       "close": closes, "volume": 1.0}, index=idx)
    df["atr"] = (high - low) if atr is None else atr
    return df


def test_uptrend_classified_positive():
    df = _frame(np.linspace(100, 200, 300))   # steady rise
    reg = classify_regime(df, adx_threshold=20.0, ma_window=50)
    # After warmup, a clean uptrend is regime +1 for most bars.
    assert (reg[100:] == 1).mean() > 0.7


def test_downtrend_classified_negative():
    df = _frame(np.linspace(200, 100, 300))
    reg = classify_regime(df, adx_threshold=20.0, ma_window=50)
    assert (reg[100:] == -1).mean() > 0.7


def test_classifier_has_no_lookahead():
    """Truncating the future cannot change an earlier bar's regime label."""
    df = _frame(np.r_[np.linspace(100, 200, 200), np.linspace(200, 100, 200)])
    full = classify_regime(df, adx_threshold=20.0, ma_window=50)
    trunc = classify_regime(df.iloc[:250], adx_threshold=20.0, ma_window=50)
    assert np.array_equal(full[:250], trunc)


# --- Task 2: short sleeve signals ---------------------------------------
from study.regime_book import short_momentum, short_mean_reversion


def test_short_momentum_fires_on_bearish_cross():
    # rise then fall: a bearish 9/21 EMA cross must appear on the way down.
    df = _frame(np.r_[np.linspace(100, 160, 120), np.linspace(160, 90, 120)])
    sig = short_momentum(df)
    assert sig.dtype == bool and len(sig) == len(df)
    assert sig[120:].any()          # fires during the decline
    assert not sig[:60].any()       # not during the clean rise


def test_short_mean_reversion_fires_on_upper_band_fade():
    # Noisy mean-reverting series, then an overbought rally that rejects the
    # upper band and reverts. Noise keeps RSI finite (a pure monotonic leg makes
    # RSI undefined/zero — a fixture artifact, not what real bars look like).
    rng = np.random.default_rng(1)
    base = 100 + np.cumsum(rng.normal(0, 0.5, 120))
    rally = base[-1] + np.cumsum(np.abs(rng.normal(0.9, 0.4, 25)))   # strong up
    revert = rally[-1] - np.cumsum(np.abs(rng.normal(0.9, 0.4, 25)))  # fade down
    df = _frame(np.r_[base, rally, revert])
    sig = short_mean_reversion(df)
    assert sig.dtype == bool and len(sig) == len(df)
    assert sig[120:].any()


# --- Task 3: regime router ----------------------------------------------
from study.regime_book import route_signals


def test_router_gates_momentum_long_to_uptrend_only():
    df = _frame(np.linspace(100, 220, 300))
    longs, shorts = route_signals(df, adx_threshold=20.0)
    reg = classify_regime(df, adx_threshold=20.0)
    # Every long entry sits in a non-downtrend bar; no shorts in a clean uptrend.
    assert all(reg[i] != -1 for i in np.flatnonzero(longs))
    assert shorts.sum() == 0 or all(reg[i] != 1 for i in np.flatnonzero(shorts))


def test_router_emits_shorts_in_downtrend():
    df = _frame(np.r_[np.linspace(100, 160, 150), np.linspace(160, 80, 150)])
    longs, shorts = route_signals(df, adx_threshold=20.0)
    assert shorts.sum() >= 1            # the decline must produce shorts


# --- Task 4: ATR-trailing exit ------------------------------------------
from study.sim import simulate_idx as _sim


def test_trailing_locks_gains_vs_fixed_bracket():
    # Long runs 100->130 then reverses to 110. TP=20 ATR (=140) is unreachable
    # and SL=96 never hits, so the FIXED book rides to the end (+9.8%). The
    # TRAILING stop ratchets up to ~4 below the 130 peak and exits the pullback
    # near 126 (+25%) — strictly better, which is the whole point.
    closes = np.r_[np.linspace(100, 130, 30), np.linspace(130, 110, 30)]
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="4h")
    df = pd.DataFrame({"close": closes, "high": closes * 1.002,
                       "low": closes * 0.998}, index=idx)
    df["atr"] = 2.0
    sig = np.zeros(len(df), bool); sig[0] = True
    fixed = _sim(df, sig, slm=2.0, tpm=20.0, direction="long")
    trail = _sim(df, sig, slm=2.0, tpm=20.0, direction="long", trail_mult=2.0)
    assert trail and fixed
    assert trail[0]["pnl_pct"] > fixed[0]["pnl_pct"]


def test_trail_mult_none_is_unchanged():
    closes = np.linspace(100, 90, 40)
    idx = pd.date_range("2024-01-01", periods=40, freq="4h")
    df = pd.DataFrame({"close": closes, "high": closes * 1.002,
                       "low": closes * 0.998}, index=idx)
    df["atr"] = 1.0
    sig = np.zeros(40, bool); sig[0] = True
    assert _sim(df, sig, 2.0, 3.0) == _sim(df, sig, 2.0, 3.0, trail_mult=None)


# --- Task 5: capped-concurrency portfolio merge -------------------------
from study.regime_book import merge_portfolio


def _trade(sym, e, x, pnl):
    return {"symbol": sym, "entry_time": pd.Timestamp(e),
            "exit_time": pd.Timestamp(x), "pnl_pct": pnl}


def test_merge_respects_concurrency_cap():
    # 3 fully-overlapping trades, cap=2 -> the 3rd (latest entry) is dropped.
    trades = [
        _trade("BTC", "2024-01-01", "2024-01-10", 0.05),
        _trade("ETH", "2024-01-02", "2024-01-09", 0.03),
        _trade("SOL", "2024-01-03", "2024-01-08", 0.02),
    ]
    kept = merge_portfolio(trades, max_concurrent=2)
    assert len(kept) == 2
    assert {t["symbol"] for t in kept} == {"BTC", "ETH"}


def test_merge_orders_by_exit_and_is_full_when_uncapped():
    trades = [
        _trade("BTC", "2024-01-05", "2024-01-06", 0.01),
        _trade("ETH", "2024-01-01", "2024-01-02", -0.02),
    ]
    kept = merge_portfolio(trades, max_concurrent=3)
    assert [t["symbol"] for t in kept] == ["ETH", "BTC"]   # exit-ordered
