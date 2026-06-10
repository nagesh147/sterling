"""Read-only paper-book demo endpoint.

Surfaces the research/paper conviction book (data/paper/*) for the dashboard.
READS FILES ONLY — imports NO study.* module, preserving the 'app never imports
study' isolation invariant. The book is DSR 0.327 < 0.5 (not deflation-provable)
and PAPER-ONLY; this endpoint never executes, mutates, or trades anything.
"""
from __future__ import annotations

import csv
import json
import os

from fastapi import APIRouter

router = APIRouter(prefix="/paper", tags=["paper"])

# Local constant (NOT imported from study, to preserve isolation). Overridable
# for tests. Matches study.paper_trader.PAPER_DIR by convention.
PAPER_DIR = os.environ.get("PAPER_DIR", "data/paper")

# Static backtest-VALIDATION result — labeled constants, never a live recompute.
_VALIDATION = {
    "dsr": 0.327,
    "oos_sharpe": 1.57,
    "oos_return_pct": 75.8,
    "is_oos_corr": 0.38,
    "provable": False,
    "verdict": ("Real out-of-sample edge (Sharpe 1.57); DSR 0.327 < 0.5 — "
                "not deflation-provable. Research/paper only, never live money."),
    "provenance": ("validated 2026-06-10; docs/funding_sleeve_result.md + "
                   "docs/regime_book_before_after.md"),
}


def _equity_curve(weighted_pnls, capital):
    """Realized (closed-trade) equity progression: cumprod(1+wp)*capital."""
    eq, v = [], float(capital)
    for p in weighted_pnls or []:
        v *= (1.0 + float(p))
        eq.append(round(v, 2))
    return eq


@router.get("/state")
def paper_state():
    """Live paper-book state (read from data/paper/state.json) + derived fields.
    Missing/unreadable file → {available: false} with 200 (demo-safe)."""
    path = os.path.join(PAPER_DIR, "state.json")
    if not os.path.exists(path):
        return {"available": False,
                "reason": "no paper state — run `python -m study.paper_trader`"}
    try:
        with open(path) as f:
            d = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"available": False, "reason": f"unreadable state: {e}"}

    capital = float(d.get("capital", 500.0)) or 500.0
    realized = d.get("realized", {}) or {}
    breaker = d.get("breaker", {}) or {}
    total_equity = float(d.get("total_equity", realized.get("end", capital)))
    return {
        "available": True,
        "total_equity": round(total_equity, 2),
        "return_pct": round((total_equity / capital - 1.0) * 100, 2),
        "realized": {k: realized.get(k) for k in ("end", "ret", "sharpe", "max_dd", "n")},
        "equity_curve": _equity_curve(realized.get("weighted_pnls"), capital),
        "open_positions": d.get("open_positions", []),
        "breaker": breaker,
        "buffer_to_trip": round((float(breaker.get("threshold", 0.0))
                                 - float(breaker.get("drawdown", 0.0))) * 100, 2),
        "tripped": bool(breaker.get("tripped", False)),
        "asof": d.get("asof"),
        "inception": d.get("inception"),
        "n_closed": d.get("n_closed", 0),
        "capital": capital,
    }


@router.get("/trades")
def paper_trades():
    """Closed-trade ledger (read from data/paper/trades.csv). pnl_pct and
    stop_dist_pct coerced to float; missing file → {available: false, trades: []}."""
    path = os.path.join(PAPER_DIR, "trades.csv")
    if not os.path.exists(path):
        return {"available": False, "trades": [], "n": 0}
    try:
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as e:
        return {"available": False, "trades": [], "n": 0, "reason": str(e)}
    for r in rows:
        for k in ("pnl_pct", "stop_dist_pct"):
            try:
                r[k] = float(r[k])
            except (TypeError, ValueError, KeyError):
                pass
    return {"available": True, "trades": rows, "n": len(rows)}


@router.get("/summary")
def paper_summary():
    """Static backtest-validation block (provenance-labeled; NOT a live recompute)."""
    return {"available": True, **_VALIDATION}
