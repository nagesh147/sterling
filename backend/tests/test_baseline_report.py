"""
Phase 5 baseline-report tests.

Exercises the in-memory `build_report` path with synthetic fixtures.
"""
import math

import numpy as np
import pytest

from baseline_report import build_report


def _make_trades(n: int, *, base_ts: int = 1_700_000_000_000) -> list:
    rng = np.random.default_rng(seed=3)
    pnls = rng.normal(0.001, 0.005, size=n)
    out = []
    for i, p in enumerate(pnls):
        out.append({
            "pnl_pct":       float(p),
            "gross_pnl_pct": float(p + 0.0008),
            "cost_pct":      0.0008,
            "regime":        "BULL" if i % 2 == 0 else "BEAR",
            "direction":     "long",
            "entry_ts_ms":   base_ts + i * 86_400_000,
            "exit_ts_ms":    base_ts + i * 86_400_000 + 3_600_000,
        })
    return out


def test_build_report_low_sample_warning():
    trades = _make_trades(5)
    rpt = build_report("BTC", "Intraday 1H", trades, signal_bar_ms=3_600_000)
    assert rpt["trade_count"] == 5
    assert any(w.startswith("low_sample_size") for w in rpt["warnings"])
    # Deflated Sharpe requires >=50 trades — should be None here.
    assert rpt["deflated_sharpe"] is None


def test_build_report_full_metrics_with_enough_trades():
    trades = _make_trades(60)
    rpt = build_report(
        "BTC", "Intraday 1H", trades, signal_bar_ms=3_600_000,
        n_trials_search=10,
    )
    assert rpt["trade_count"] == 60
    assert rpt["deflated_sharpe"] is not None
    assert rpt["sharpe"] is not None
    assert rpt["sharpe_method"] == "calendar_daily"
    assert rpt["cagr"] is not None
    assert "BULL" in rpt["regime_breakdown"]


def test_build_report_cost_aggregation_matches_inputs():
    trades = _make_trades(40)
    rpt = build_report("BTC", "1H", trades, signal_bar_ms=3_600_000)
    expected_cost = sum(t["cost_pct"] for t in trades)
    expected_gross = sum(t["gross_pnl_pct"] for t in trades)
    expected_net  = sum(t["pnl_pct"] for t in trades)
    assert rpt["cost_drag_sum"] == pytest.approx(expected_cost, abs=1e-6)
    assert rpt["gross_pnl_sum"] == pytest.approx(expected_gross, abs=1e-6)
    assert rpt["net_pnl_sum"]   == pytest.approx(expected_net,   abs=1e-6)


def test_build_report_empty_trades_safe():
    rpt = build_report("BTC", "1H", [], signal_bar_ms=3_600_000)
    assert rpt["trade_count"] == 0
    assert rpt["profit_factor"] is None
    assert "low_sample_size" in "".join(rpt["warnings"])


def test_build_report_marks_thin_regime():
    """Regime buckets below MIN_TRADES_PER_REGIME flagged as thin."""
    base_ts = 1_700_000_000_000
    rng = np.random.default_rng(seed=7)
    pnls = rng.normal(0.001, 0.005, size=40)
    trades = []
    for i, p in enumerate(pnls):
        regime = "BULL" if i < 35 else "VOLATILE"  # only 5 VOLATILE
        trades.append({
            "pnl_pct":       float(p),
            "gross_pnl_pct": float(p + 0.0008),
            "cost_pct":      0.0008,
            "regime":        regime,
            "entry_ts_ms":   base_ts + i * 86_400_000,
            "exit_ts_ms":    base_ts + i * 86_400_000 + 3_600_000,
        })
    rpt = build_report("BTC", "1H", trades, signal_bar_ms=3_600_000)
    assert rpt["regime_breakdown"]["VOLATILE"].get("thin_sample") is True
    assert any("VOLATILE" in w for w in rpt["warnings"])
