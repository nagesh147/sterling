import numpy as np
import pandas as pd
import pytest
from app.engines.sterling_v2 import data as v2data
from app.engines.sterling_v2.config import SimConfig
from app.engines.sterling_v2 import harness as H
from app.engines.edge.strategies import SIGNAL_FNS


def _btc_path_or_skip():
    path = v2data.list_symbols().get("BTCUSD")
    if not path:
        pytest.skip("optional Sterling V2 BTC parquet dataset is not installed")
    return path


def test_list_symbols_reports_mapping_when_dataset_is_available():
    syms = v2data.list_symbols()
    assert isinstance(syms, dict)
    if syms:
        assert all(isinstance(symbol, str) and path for symbol, path in syms.items())


def test_resample_4h_has_atr():
    df = v2data.load_symbol(_btc_path_or_skip())
    d4 = v2data.resample_tf(df, "4h")
    assert "atr" in d4.columns and len(d4) > 1000


def _synth(prices):
    """Build an OHLC df from a close path; open=prev close, hi/lo padded, ATR const."""
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="4h")
    close = np.array(prices, float)
    open_ = np.concatenate([[close[0]], close[:-1]])
    df = pd.DataFrame({
        "open": open_, "high": np.maximum(open_, close) * 1.001,
        "low": np.minimum(open_, close) * 0.999, "close": close,
        "volume": 1.0, "atr": 1.0,
    }, index=idx)
    return df


def test_entry_fills_next_bar_open():
    df = _synth([100, 110, 121, 133])
    sigs = np.array([True, False, False, False])
    cfg = SimConfig(sl_mult=99, tp_mult=99, slippage=0.0, fee_round_trip=0.0,
                    max_hold_bars=2)
    res = H.simulate(df, sigs, None, cfg)
    assert res.entry_times[0] == df.index[1]


def test_costs_make_flat_trade_negative():
    df = _synth([100, 100, 100, 100, 100])
    sigs = np.array([True, False, False, False, False])
    cfg = SimConfig(sl_mult=99, tp_mult=99, slippage=0.0005, fee_round_trip=0.001,
                    max_hold_bars=2)
    res = H.simulate(df, sigs, None, cfg)
    assert res.returns[0] < 0


def test_sharpe_annualization_uses_realized_frequency():
    idx = pd.date_range("2024-01-01", periods=51, freq="7D")
    rng = np.random.default_rng(0)
    r = rng.normal(0.01, 0.05, 50)
    res = H.SimResult(r, list(idx[:50]), [1] * 50, [1] * 50, idx)
    m = H.compute_metrics(res)
    expected = r.mean() / r.std(ddof=1) * np.sqrt(m["trades_per_year"])
    assert abs(m["sharpe"] - expected) < 1e-9
    assert 45 < m["trades_per_year"] < 55


def test_short_side_profits_on_downtrend():
    df = _synth([100, 90, 81, 73])
    shorts = np.array([True, False, False, False])
    cfg = SimConfig(sl_mult=99, tp_mult=0.05, slippage=0.0, fee_round_trip=0.0,
                    max_hold_bars=2, allow_short=True)
    res = H.simulate(df, np.zeros(4, bool), shorts, cfg)
    assert res.sides[0] == -1 and res.returns[0] > 0


def test_final_bar_time_exit_closes_trade():
    df = _synth([100, 101, 102, 103])
    sigs = np.array([True, False, False, False])
    cfg = SimConfig(sl_mult=99, tp_mult=99, slippage=0.0, fee_round_trip=0.0,
                    max_hold_bars=2)
    res = H.simulate(df, sigs, None, cfg)
    assert len(res.returns) == 1 and res.bars_held[0] == 2


def test_signal_on_last_bar_yields_no_trade():
    df = _synth([100, 101, 102, 103])
    sigs = np.array([False, False, False, True])
    cfg = SimConfig(sl_mult=99, tp_mult=99, max_hold_bars=2)
    res = H.simulate(df, sigs, None, cfg)
    assert len(res.returns) == 0


def test_both_touched_resolves_sl_first_long():
    idx = pd.date_range("2024-01-01", periods=3, freq="4h")
    df = pd.DataFrame({
        "open": [100.0, 100.0, 100.0],
        "high": [100.0, 102.0, 100.0],
        "low": [100.0, 98.0, 100.0],
        "close": [100.0, 100.0, 100.0],
        "volume": 1.0, "atr": 1.0,
    }, index=idx)
    sigs = np.array([True, False, False])
    cfg = SimConfig(sl_mult=1.0, tp_mult=1.0, slippage=0.0, fee_round_trip=0.0,
                    max_hold_bars=99)
    res = H.simulate(df, sigs, None, cfg)
    assert res.returns[0] < 0


def test_exit_policy_trailing_locks_in_more_than_static():
    from app.engines.sterling_v2.exits import TrailingExit
    df = _synth([100, 102, 105, 110, 115, 112, 108, 104, 100])
    sigs = np.array([True] + [False] * 8)
    cfg = SimConfig(sl_mult=2.0, tp_mult=99, slippage=0.0, fee_round_trip=0.0,
                    max_hold_bars=7)
    static = H.simulate(df, sigs, None, cfg)
    trailed = H.simulate(df, sigs, None, cfg, exit_policy=TrailingExit(1.5, 1.0))
    assert len(static.returns) == 1 and len(trailed.returns) == 1
    assert trailed.returns[0] > static.returns[0]
    assert trailed.bars_held[0] < static.bars_held[0]


def test_exit_policy_does_not_fire_on_entry_bar():
    from app.engines.sterling_v2.exits import TrailingExit
    df = _synth([100, 101, 102, 103])
    sigs = np.array([True, False, False, False])
    cfg = SimConfig(sl_mult=2.0, tp_mult=99, slippage=0.0, fee_round_trip=0.0,
                    max_hold_bars=2)
    res = H.simulate(df, sigs, None, cfg, exit_policy=TrailingExit(1.5, 1.0))
    assert len(res.returns) == 1 and res.bars_held[0] >= 1


def test_btc_ma_crossover_matches_grounding():
    """Validate the independent BTC grounding only when its optional dataset exists."""
    df = v2data.load_symbol(_btc_path_or_skip())
    d4 = v2data.resample_tf(df, "4h")
    sigs = SIGNAL_FNS["ma_crossover"](d4)
    cfg = SimConfig(sl_mult=2.0, tp_mult=3.5, fee_round_trip=0.001,
                    slippage=0.0005, max_hold_bars=200)
    m = H.compute_metrics(H.simulate(d4, sigs, None, cfg))
    assert 150 <= m["trades"] <= 175
    assert 0.38 <= m["win"] <= 0.47
    assert 1.15 <= m["pf"] <= 1.35
    assert -0.32 <= m["max_dd"] <= -0.24
    assert 0.70 <= m["sharpe"] <= 1.00
