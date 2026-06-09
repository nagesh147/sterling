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


# --- Task 6: pooled book builder + walk-forward -------------------------
from study.regime_book import build_symbol_trades, portfolio_equity, walk_forward_book


def test_build_symbol_trades_tags_symbol_and_times():
    df = _frame(np.r_[np.linspace(100, 160, 150), np.linspace(160, 80, 150)])
    df["atr"] = 2.0
    trades = build_symbol_trades("BTC", df, adx_threshold=20.0)
    assert trades, "expected at least one routed trade"
    assert all(t["symbol"] == "BTC" for t in trades)
    assert all({"entry_time", "exit_time", "pnl_pct"} <= t.keys() for t in trades)


def test_portfolio_equity_weights_by_cap():
    # one +10% trade, cap=2 -> book grows by ~ (1 + 0.10/2).
    trades = [{"symbol": "BTC", "entry_time": pd.Timestamp("2024-01-01"),
               "exit_time": pd.Timestamp("2024-01-02"), "pnl_pct": 0.10}]
    eq = portfolio_equity(trades, cap=500.0, max_concurrent=2)
    assert eq["end"] == pytest.approx(500.0 * (1 + 0.10 / 2), rel=1e-6)


def test_walk_forward_book_runs_and_is_leakfree_shape():
    frames = {}
    rng = np.random.default_rng(0)
    for sym in ("BTC", "ETH", "SOL"):
        c = 100 + np.cumsum(rng.normal(0, 1, 800))
        c = np.clip(c, 10, None)
        idx = pd.date_range("2024-01-01", periods=800, freq="4h")
        d = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99,
                          "close": c, "volume": 1.0}, index=idx)
        d["atr"] = (d["high"] - d["low"]).rolling(14).mean().bfill()
        frames[sym] = d
    res = walk_forward_book(frames, adx_threshold=20.0, use_regime=True)
    assert {"oos", "dsr", "beats_hold", "n"} <= res.keys()
    assert res["n"] >= 0


def test_basket_hodl_is_not_cross_symbol_concat_artifact():
    """Equal-weight basket HODL: 3 symbols each falling ~50% over the OOS span
    must give a basket net_return near -50% — NOT the absurd value you'd get by
    concatenating raw prices ($70k→$3k→$150 boundary jumps)."""
    from study.regime_book import _basket_hodl
    frames = {}
    for sym, lvl in (("BTC", 70000.0), ("ETH", 3000.0), ("SOL", 150.0)):
        c = np.linspace(lvl, lvl * 0.5, 400)   # each halves over the window
        idx = pd.date_range("2024-01-01", periods=400, freq="4h")
        frames[sym] = pd.DataFrame({"close": c}, index=idx)
    h = _basket_hodl(frames, oos_start=0.0)   # full window: each halves
    assert h["net_return"] == pytest.approx(-0.5, abs=0.01)   # ~ -50% (minus fee)
    assert -0.55 < h["max_drawdown"] <= 0.0


# --- Upgrade: vol-target sizing + sleeve-specific exits ------------------
from study.regime_book import (
    vol_target_weight, build_symbol_trades_sleeved, portfolio_equity_sized,
)


def test_vol_target_equalizes_risk_across_atr():
    # Same risk budget, different ATR -> size scales inversely so a stop-out
    # costs the SAME fraction of equity either way.
    w_lo = vol_target_weight(entry=100, atr=2.0, slm=1.5, risk_per_trade=0.015, max_leverage=10)
    w_hi = vol_target_weight(entry=100, atr=4.0, slm=1.5, risk_per_trade=0.015, max_leverage=10)
    assert w_lo == pytest.approx(0.5)    # stop_dist 0.03 -> 0.015/0.03
    assert w_hi == pytest.approx(0.25)   # stop_dist 0.06 -> 0.015/0.06
    assert w_lo * (1.5 * 2.0 / 100) == pytest.approx(0.015)   # equal risk
    assert w_hi * (1.5 * 4.0 / 100) == pytest.approx(0.015)


def test_vol_target_caps_at_max_leverage():
    # A near-zero stop would imply enormous size — the leverage cap binds.
    assert vol_target_weight(100, atr=0.05, slm=1.5, risk_per_trade=0.02,
                             max_leverage=3.0) == 3.0


def test_sleeved_builder_tags_sleeve_and_stop_distance():
    df = _frame(np.r_[np.linspace(100, 160, 150), np.linspace(160, 80, 150)])
    df["atr"] = 2.0
    trades = build_symbol_trades_sleeved("BTC", df, adx_threshold=20.0)
    assert trades
    assert {t["sleeve"] for t in trades} <= {"trend", "mr"}
    assert all(t["stop_dist_pct"] > 0 for t in trades)
    assert all(t["symbol"] == "BTC" for t in trades)


def test_sized_equity_leverage_scales_return():
    # Same trades, 2x leverage -> ~2x the (small) book return contribution.
    trades = [{"symbol": "BTC", "sleeve": "mr", "direction": "long",
               "entry_time": pd.Timestamp("2024-01-01"),
               "exit_time": pd.Timestamp("2024-01-02"),
               "pnl_pct": 0.04, "stop_dist_pct": 0.04}]
    e1 = portfolio_equity_sized(trades, cap=500.0, risk_per_trade=0.02,
                                max_leverage=10, max_concurrent=3, leverage=1.0)
    e2 = portfolio_equity_sized(trades, cap=500.0, risk_per_trade=0.02,
                                max_leverage=10, max_concurrent=3, leverage=2.0)
    # w = 0.02/0.04 = 0.5; contrib_1x = 0.5*0.04 = 0.02 ; contrib_2x = 1.0*0.04 = 0.04
    assert e1["ret"] == pytest.approx(0.02, rel=1e-6)
    assert e2["ret"] == pytest.approx(0.04, rel=1e-6)


def test_conviction_mr_signals_are_subset_of_loose():
    """Tighter RSI thresholds must select a strict subset of the loose sleeve —
    conviction concentration takes fewer, deeper-extreme setups."""
    from study.regime_book import _mr_signals
    rng = np.random.default_rng(3)
    c = np.clip(100 + np.cumsum(rng.normal(0, 1, 600)), 5, None)
    df = _frame(c)
    base_l, base_s = _mr_signals(df, rsi_lo=40, rsi_hi=60)
    conv_l, conv_s = _mr_signals(df, rsi_lo=25, rsi_hi=75)
    assert (conv_l & ~base_l).sum() == 0          # subset (long)
    assert (conv_s & ~base_s).sum() == 0          # subset (short)
    assert conv_l.sum() <= base_l.sum()           # fewer setups
    assert conv_s.sum() <= base_s.sum()


def test_sleeved_builder_accepts_conviction_thresholds():
    df = _frame(np.r_[np.linspace(100, 160, 200), np.linspace(160, 80, 200)])
    df["atr"] = 2.0
    loose = build_symbol_trades_sleeved("BTC", df, adx_threshold=20.0,
                                        rsi_lo=40, rsi_hi=60)
    conv = build_symbol_trades_sleeved("BTC", df, adx_threshold=20.0,
                                       rsi_lo=25, rsi_hi=75)
    n_loose_mr = sum(1 for t in loose if t["sleeve"] == "mr")
    n_conv_mr = sum(1 for t in conv if t["sleeve"] == "mr")
    assert n_conv_mr <= n_loose_mr


def _random_frames(n=700, seed=0):
    frames = {}
    rng = np.random.default_rng(seed)
    for sym in ("BTC", "ETH", "SOL"):
        c = np.clip(100 + np.cumsum(rng.normal(0, 1, n)), 10, None)
        idx = pd.date_range("2024-01-01", periods=n, freq="4h")
        d = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99,
                          "close": c, "volume": 1.0}, index=idx)
        d["atr"] = (d["high"] - d["low"]).rolling(14).mean().bfill()
        frames[sym] = d
    return frames


def test_conviction_selection_uses_in_sample_only():
    """The chosen config must be the in-sample-Sharpe maximiser — never chosen
    for its OOS result. A config with great OOS but poor IS must not win."""
    from study.regime_book import select_conviction_book, conviction_grid
    frames = _random_frames()
    grid = conviction_grid()[:6]
    res = select_conviction_book(frames, grid=grid)
    chosen_is = res["chosen"]["is_sharpe"]
    assert chosen_is == max(s["is_sharpe"] for s in res["scored"])  # IS-driven
    assert res["n_grid"] == len(grid)
    assert 0.0 <= res["dsr"] <= 1.0


def test_leverage_dial_sharpe_invariant():
    """Leverage scales return/drawdown but NOT Sharpe (the core honest truth)."""
    from study.regime_book import leverage_dial
    trades = [{"symbol": "BTC", "sleeve": "mr", "direction": "long",
               "entry_time": pd.Timestamp(f"2024-01-{d:02d}"),
               "exit_time": pd.Timestamp(f"2024-01-{d:02d} 12:00"),
               "pnl_pct": p, "stop_dist_pct": 0.04}
              for d, p in [(1, 0.05), (3, -0.03), (5, 0.06), (7, -0.02), (9, 0.04)]]
    rows = leverage_dial(trades, levels=(1.0, 2.0, 3.0))
    sharpes = {round(r["sharpe"], 6) for r in rows}
    assert len(sharpes) == 1                       # identical across leverage
    assert rows[1]["ret"] > rows[0]["ret"]         # 2x lifts return (edge +ve)
