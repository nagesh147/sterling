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


# --- robustness gate (OOS Sharpe + Monte-Carlo P(loss)) ------------------

_RHEADER = ("symbol,tf,strategy,profile,trades,win_rate,pf,sharpe,expectancy,"
            "net_return,pnl_usd,max_dd,oos_sharpe,p_loss\n")


def _rrow(sym, tf, strat, prof, trades, sharpe, net, oos, ploss, pf=1.2, exp=0.003):
    return (f"{sym},{tf},{strat},{prof},{trades},0.42,{pf},{sharpe},{exp},"
            f"{net},300,-0.3,{oos},{ploss}\n")


def _write_rcsv(tmp_path, rows):
    p = tmp_path / "robust.csv"
    p.write_text(_RHEADER + "".join(rows))
    return str(p)


def test_missing_robustness_columns_are_backward_compatible(tmp_path):
    """Old CSVs without oos_sharpe/p_loss still load under a robustness gate."""
    csv = _write_csv(tmp_path, [
        _row("BTCUSD", "4h", "ma_crossover", "Intraday", 166, 1.83, 0.953),
    ])
    reg = load_edge_registry(csv, gate=EdgeGate(min_oos_sharpe=0.0, max_p_loss=0.35))
    assert reg.allowed("BTCUSD", "4h", "ma_crossover", "Intraday")


def test_negative_oos_sharpe_rejected_by_robustness_gate(tmp_path):
    csv = _write_rcsv(tmp_path, [
        # strong in-sample but OOS Sharpe collapses → reject
        _rrow("BTCUSD", "4h", "mean_reversion", "Intraday", 104, 1.5, 0.30, oos=-0.2, ploss=0.4),
    ])
    reg = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.0, min_trades=20,
                                                min_oos_sharpe=0.0, max_p_loss=0.35))
    assert not reg.allowed("BTCUSD", "4h", "mean_reversion", "Intraday")


def test_high_p_loss_rejected(tmp_path):
    csv = _write_rcsv(tmp_path, [
        _rrow("ETHUSD", "2h", "smc", "Aggressive", 240, 0.91, 0.46, oos=5.2, ploss=0.45),
    ])
    reg = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.0, min_trades=20,
                                                min_oos_sharpe=0.0, max_p_loss=0.35))
    assert not reg.allowed("ETHUSD", "2h", "smc", "Aggressive")


def test_robust_survivor_with_low_raw_sharpe_admitted(tmp_path):
    """price_action 1h: raw Sharpe 0.69 (< old 0.8 gate) but survives OOS + MC.
    The robustness gate must admit it by relaxing raw Sharpe."""
    csv = _write_rcsv(tmp_path, [
        _rrow("BTCUSD", "1h", "price_action", "Intraday", 434, 0.69, 0.39, oos=3.97, ploss=0.24),
    ])
    reg = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.0, min_trades=20,
                                                min_oos_sharpe=0.0, max_p_loss=0.35))
    assert reg.allowed("BTCUSD", "1h", "price_action", "Intraday")
    c = reg.get("BTCUSD", "1h", "price_action", "Intraday")
    assert c.oos_sharpe == pytest.approx(3.97)
    assert c.p_loss == pytest.approx(0.24)


# --- deflation gate (DSR) + buy-and-hold requirement ---------------------

_DHEADER = ("symbol,tf,strategy,profile,trades,win_rate,pf,sharpe,expectancy,"
            "net_return,pnl_usd,max_dd,oos_sharpe,p_loss,dsr,beats_hold\n")


def _drow(sym, tf, strat, prof, trades, sharpe, net, oos, ploss, dsr,
          beats_hold, pf=1.2, exp=0.003):
    return (f"{sym},{tf},{strat},{prof},{trades},0.42,{pf},{sharpe},{exp},"
            f"{net},300,-0.3,{oos},{ploss},{dsr},{beats_hold}\n")


def _write_dcsv(tmp_path, rows):
    p = tmp_path / "deflated.csv"
    p.write_text(_DHEADER + "".join(rows))
    return str(p)


def test_low_dsr_rejected_by_deflation_gate(tmp_path):
    """The real #1 config: huge in-sample return, positive OOS, beats hold —
    but DSR 0.35 means it fails multiple-testing deflation. A min_dsr=0.5 gate
    must reject it; a min_dsr=0.0 gate (no-op) must admit it."""
    csv = _write_dcsv(tmp_path, [
        _drow("BTCUSD", "4h", "bb_rsi_reversion", "Aggressive", 91, 2.63, 0.991,
              oos=0.02, ploss=0.20, dsr=0.35, beats_hold=True),
    ])
    strict = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.0, min_trades=20,
                                                   min_dsr=0.5))
    loose = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.0, min_trades=20,
                                                  min_dsr=0.0))
    assert not strict.allowed("BTCUSD", "4h", "bb_rsi_reversion", "Aggressive")
    assert loose.allowed("BTCUSD", "4h", "bb_rsi_reversion", "Aggressive")


def test_loser_to_buy_and_hold_rejected_when_required(tmp_path):
    """A config that clears every stat gate but underperforms buy-and-hold has
    no reason to trade. require_beats_hold=True must reject it."""
    csv = _write_dcsv(tmp_path, [
        _drow("BTCUSD", "4h", "vwap_cross", "Intraday", 94, 1.5, 0.476,
              oos=0.5, ploss=0.20, dsr=0.9, beats_hold=False),
    ])
    req = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.0, min_trades=20,
                                                require_beats_hold=True))
    off = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.0, min_trades=20,
                                                require_beats_hold=False))
    assert not req.allowed("BTCUSD", "4h", "vwap_cross", "Intraday")
    assert off.allowed("BTCUSD", "4h", "vwap_cross", "Intraday")


def test_dsr_and_beats_hold_columns_backward_compatible(tmp_path):
    """Legacy CSV with no dsr/beats_hold columns still loads under a strict
    gate — missing columns behave as pass, matching the oos/p_loss convention."""
    csv = _write_csv(tmp_path, [
        _row("BTCUSD", "4h", "ma_crossover", "Intraday", 166, 1.83, 0.953),
    ])
    reg = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.0, min_trades=20,
                                                min_dsr=0.5, require_beats_hold=True))
    assert reg.allowed("BTCUSD", "4h", "ma_crossover", "Intraday")


def test_combo_carries_dsr_and_beats_hold(tmp_path):
    csv = _write_dcsv(tmp_path, [
        _drow("BTCUSD", "4h", "bb_rsi_reversion", "Aggressive", 91, 2.63, 0.991,
              oos=0.02, ploss=0.20, dsr=0.353, beats_hold=True),
    ])
    reg = load_edge_registry(csv, gate=EdgeGate(min_sharpe=0.0, min_trades=20))
    c = reg.get("BTCUSD", "4h", "bb_rsi_reversion", "Aggressive")
    assert c.dsr == pytest.approx(0.353)
    assert c.beats_hold is True


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
