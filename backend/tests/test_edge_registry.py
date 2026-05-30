"""Edge registry — load backtest_edge_results.csv, gate by threshold, score.

The registry is what stops the live edge feed from emitting signals for combos
that lost money or only "won" on a handful of trades. Default gate:
net_return > 0  AND  sharpe >= 0.8  AND  trades >= 50.
"""
from __future__ import annotations

import os

import pytest

from app.engines.edge.registry import (
    EdgeGate,
    load_edge_registry,
    signal_score_from_metrics,
)

_HEADER = ("symbol,tf,strategy,profile,trades,win_rate,pf,sharpe,expectancy,"
           "gross_profit,gross_loss,net_return,end_capital,pnl_usd,max_dd\n")


def _row(symbol, tf, strat, prof, trades, sharpe, net_return, pf=1.2, exp=0.003):
    return (f"{symbol},{tf},{strat},{prof},{trades},0.42,{pf},{sharpe},{exp},"
            f"1000,800,{net_return},800,300,-0.3\n")


def _write_csv(tmp_path, rows):
    p = tmp_path / "edge.csv"
    p.write_text(_HEADER + "".join(rows))
    return str(p)


def test_winner_passes_default_gate(tmp_path):
    csv = _write_csv(tmp_path, [
        _row("BTCUSD", "4h", "ma_crossover", "Intraday", 166, 1.83, 0.953),
    ])
    reg = load_edge_registry(csv)
    assert reg.allowed("BTCUSD", "4h", "ma_crossover", "Intraday")
    assert len(reg.all()) == 1


def test_low_sharpe_rejected(tmp_path):
    csv = _write_csv(tmp_path, [
        _row("BTCUSD", "4h", "smc", "Scalping", 221, 0.0, -0.055),
    ])
    reg = load_edge_registry(csv)
    assert not reg.allowed("BTCUSD", "4h", "smc", "Scalping")
    assert reg.all() == []


def test_negative_net_return_rejected(tmp_path):
    csv = _write_csv(tmp_path, [
        # sharpe high but lost money — must not pass
        _row("BTCUSD", "4h", "breakout", "Scalping", 148, 1.5, -0.093),
    ])
    reg = load_edge_registry(csv)
    assert not reg.allowed("BTCUSD", "4h", "breakout", "Scalping")


def test_too_few_trades_rejected(tmp_path):
    csv = _write_csv(tmp_path, [
        _row("SOLUSD", "4h", "ma_crossover", "Intraday", 12, 3.0, 2.0),
    ])
    reg = load_edge_registry(csv)
    assert not reg.allowed("SOLUSD", "4h", "ma_crossover", "Intraday")


def test_gate_is_configurable(tmp_path):
    csv = _write_csv(tmp_path, [
        _row("ETHUSD", "1h", "price_action", "Intraday", 60, 0.5, 0.10),
    ])
    strict = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.8))
    loose = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.4))
    assert not strict.allowed("ETHUSD", "1h", "price_action", "Intraday")
    assert loose.allowed("ETHUSD", "1h", "price_action", "Intraday")


def test_combo_carries_metrics(tmp_path):
    csv = _write_csv(tmp_path, [
        _row("BTCUSD", "4h", "ma_crossover", "Intraday", 166, 1.83, 0.953, pf=1.29),
    ])
    reg = load_edge_registry(csv)
    combo = reg.get("BTCUSD", "4h", "ma_crossover", "Intraday")
    assert combo.sharpe == pytest.approx(1.83)
    assert combo.pf == pytest.approx(1.29)
    assert combo.trades == 166
    assert 0.0 <= combo.signal_score <= 100.0


# --- scoring -------------------------------------------------------------

def test_score_monotonic_in_sharpe():
    lo = signal_score_from_metrics(sharpe=0.5, expectancy=0.001, pf=1.05)
    hi = signal_score_from_metrics(sharpe=1.8, expectancy=0.001, pf=1.05)
    assert hi > lo


def test_score_clamped_0_100():
    assert signal_score_from_metrics(sharpe=99, expectancy=9, pf=99) <= 100.0
    assert signal_score_from_metrics(sharpe=-99, expectancy=-9, pf=0) >= 0.0


# --- real CSV smoke ------------------------------------------------------

_REAL_CSV = os.path.join(os.path.dirname(__file__), "..", "..",
                         "backtest_edge_results.csv")


@pytest.mark.skipif(not os.path.exists(_REAL_CSV), reason="results CSV absent")
def test_real_csv_admits_winner_rejects_subhour():
    reg = load_edge_registry(_REAL_CSV)
    # The documented #1 winner must be admitted.
    assert reg.allowed("BTCUSD", "4h", "ma_crossover", "Intraday")
    # Sub-hour combos bleed to fees — none should pass.
    assert not any(c.tf in ("1m", "5m", "15m") for c in reg.all())
