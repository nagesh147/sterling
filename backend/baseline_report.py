"""
TTACE Phase 5 — baseline report script.

Generates a truthful post-fix baseline report from a list of completed
backtest trades. The report is intentionally conservative: it surfaces
sample-size warnings whenever a metric is statistically thin, and refuses
to pretend a result is significant when it isn't.

The script has two entry points:

  * `build_report(asset, profile, trades, equity_curve, signal_bar_ms)`
    Pure function that returns a serialisable report dict from in-memory
    trades / equity curve. This is what the tests exercise — no I/O.

  * `python baseline_report.py --fixtures <path>` (CLI)
    Loads a fixture JSON (matching the dict schema below) and prints the
    report. Useful for manual inspection. The script intentionally does
    NOT load from the live SQLite positions table: aggregate stats there
    are pre-TTACE and contaminated.

Fixture / input shape:

    {
      "asset": "BTC",
      "profile": "Intraday 1H",
      "signal_bar_ms": 3600000,
      "trades": [
        {"pnl_pct": ..., "gross_pnl_pct": ..., "net_pnl_pct": ...,
         "cost_pct": ..., "regime": "BULL", "direction": "long",
         "entry_ts_ms": ..., "exit_ts_ms": ...},
        ...
      ],
      "equity_curve": [1.0, 1.01, ...]   // optional, derived if missing
    }
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np

from app.engines.analytics.performance import (
    full_report, deflated_sharpe,
)


_MIN_TRADES_FOR_METRICS  = 30
_MIN_TRADES_FOR_DEFLATED = 50
_MIN_TRADES_PER_REGIME   = 10


def _build_curve(trades: List[Dict[str, Any]]) -> np.ndarray:
    pnls = [float(t["pnl_pct"]) for t in trades]
    if not pnls:
        return np.array([1.0])
    curve = np.ones(len(pnls) + 1, dtype=np.float64)
    for i, p in enumerate(pnls):
        curve[i + 1] = curve[i] * (1.0 + p)
    return curve


def _aggregate_costs(trades: List[Dict[str, Any]]) -> Dict[str, float]:
    if not trades:
        return {"gross_pnl_pct_sum": 0.0, "net_pnl_pct_sum": 0.0,
                "cost_drag_pct_sum": 0.0, "avg_net_pnl_pct": 0.0}
    gross = sum(float(t.get("gross_pnl_pct", t["pnl_pct"])) for t in trades)
    cost  = sum(float(t.get("cost_pct", 0.0)) for t in trades)
    net   = sum(float(t["pnl_pct"]) for t in trades)
    return {
        "gross_pnl_pct_sum": gross,
        "cost_drag_pct_sum": cost,
        "net_pnl_pct_sum":   net,
        "avg_net_pnl_pct":   net / len(trades),
    }


def build_report(
    asset: str,
    profile: str,
    trades: List[Dict[str, Any]],
    *,
    equity_curve: Optional[List[float]] = None,
    signal_bar_ms: Optional[int] = None,
    n_trials_search: int = 1,
) -> Dict[str, Any]:
    """
    Compose a truthful baseline report from completed-trade records.

    `n_trials_search` is the number of independent strategies / parameter
    combinations explored to arrive at this result. Passing the count that
    was actually searched honours the deflated-Sharpe formula.
    """
    n = len(trades)
    warnings: List[str] = []
    if n < _MIN_TRADES_FOR_METRICS:
        warnings.append(
            f"low_sample_size:n={n}<{_MIN_TRADES_FOR_METRICS}"
        )

    curve = (np.asarray(equity_curve, dtype=np.float64)
             if equity_curve is not None else _build_curve(trades))
    rpt = full_report(curve, trades, signal_bar_ms=signal_bar_ms)
    costs = _aggregate_costs(trades)

    # Regime breakdown with thin-bucket warnings
    regimes_with_warning: Dict[str, Dict[str, Any]] = {}
    for regime, bucket in rpt.regime_breakdown.items():
        bw = dict(bucket)
        if bucket["trade_count"] < _MIN_TRADES_PER_REGIME:
            bw["thin_sample"] = True
            warnings.append(f"thin_regime:{regime}:n={bucket['trade_count']}")
        regimes_with_warning[regime] = bw

    deflated: Optional[float] = None
    if n >= _MIN_TRADES_FOR_DEFLATED:
        deflated = deflated_sharpe(
            observed_sharpe=rpt.sharpe,
            n_trials=max(1, int(n_trials_search)),
            n_observations=n,
        )

    return {
        "asset":           asset,
        "profile":         profile,
        "trade_count":     n,
        "win_rate":        round(rpt.win_rate, 4),
        "profit_factor":   (None if rpt.profit_factor is None
                            else (math.inf if rpt.profit_factor == math.inf
                                  else round(rpt.profit_factor, 4))),
        "sharpe":          round(rpt.sharpe, 4),
        "sortino":         round(rpt.sortino, 4),
        "calmar":          round(rpt.calmar, 4),
        "cagr":            None if rpt.cagr is None else round(rpt.cagr, 6),
        "max_drawdown":    round(rpt.max_drawdown, 6),
        "ulcer_index":     round(rpt.ulcer_index, 4),
        "pain_ratio":      round(rpt.pain_ratio, 4),
        "tail_ratio":      None if rpt.tail_ratio is None else round(rpt.tail_ratio, 4),
        "avg_net_pnl_pct": round(costs["avg_net_pnl_pct"], 6),
        "gross_pnl_sum":   round(costs["gross_pnl_pct_sum"], 6),
        "cost_drag_sum":   round(costs["cost_drag_pct_sum"], 6),
        "net_pnl_sum":     round(costs["net_pnl_pct_sum"], 6),
        "deflated_sharpe": None if deflated is None else round(deflated, 4),
        "sharpe_method":   rpt.sharpe_method,
        "regime_breakdown": regimes_with_warning,
        "warnings":        warnings,
    }


def _cli(argv: List[str]) -> int:
    p = argparse.ArgumentParser(description="TTACE baseline report")
    p.add_argument("--fixtures", required=True,
                   help="Path to a JSON file containing a trade fixture")
    p.add_argument("--n-trials", type=int, default=1,
                   help="Number of independent strategies searched")
    p.add_argument("--out", default=None,
                   help="Write report JSON here (default: stdout)")
    args = p.parse_args(argv)

    with open(args.fixtures, "r", encoding="utf-8") as f:
        fx = json.load(f)
    rpt = build_report(
        asset=fx.get("asset", ""),
        profile=fx.get("profile", ""),
        trades=fx.get("trades", []),
        equity_curve=fx.get("equity_curve"),
        signal_bar_ms=fx.get("signal_bar_ms"),
        n_trials_search=args.n_trials,
    )
    payload = json.dumps(rpt, indent=2, default=str)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as g:
            g.write(payload)
    else:
        print(payload)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.path.insert(0, os.path.dirname(__file__))
    raise SystemExit(_cli(sys.argv[1:]))
