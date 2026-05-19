"""
Tier B #12 — Live vs. Backtest Execution Reconciliation.

Pure functions: no DB, no `time.time()`, no exchange calls. Caller supplies a
chronologically ordered list of trade dicts, each carrying both the
backtested-expected return and the realised live/paper return for the same
setup. Output captures the per-trade drift, its rolling 5-trade standard
deviation, and a HALT recommendation when the most recent drift is more than
2σ below the rolling mean (i.e. the live engine is leaking edge faster than
the noise band justifies).

Trade dict contract (all keys looked up via `.get`, missing → None):

    {
      "expected_pnl_pct":  float,   # backtested expected return for this setup
      "realized_pnl_pct":  float,   # paper / live realised return
      "exit_ts_ms":        int,     # optional; preserved in the per-trade row
      ...
    }

The reconciler skips trades where either expected or realised is missing —
those are not "executions" and shouldn't move the drift series.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np


# Rolling window over which we compute the drift std-deviation band.
_ROLLING_WINDOW = 5
# Drift must be this many standard deviations BELOW the rolling mean before we
# recommend halting. Negative-only because positive drift (realised > expected)
# is upside surprise, not a danger.
_HALT_SIGMA_THRESHOLD = 2.0


def _safe_float(value: Any) -> Optional[float]:
    """Coerce to float or return None for any non-numeric / missing input."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def reconcile_execution(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute the rolling expected-vs-realised drift series and an alert flag.

    Per trade:
        drift = realized_pnl_pct - expected_pnl_pct        (sign-preserving)

    Over the trailing 5 trades:
        mean   = mean(drift_window)
        std    = sample std of drift_window (ddof=1)
        z      = (drift[-1] - mean) / std                  (NaN if std == 0)

    Output:
        {
          "n_trades":           int,             # # of trades with both legs present
          "drift_series":       [ {drift, expected, realized, exit_ts_ms}, ... ],
          "rolling_window":     5,
          "current_drift":      float | None,
          "rolling_mean":       float | None,
          "rolling_std":        float | None,
          "current_z":          float | None,
          "alert":              str  | None,    # e.g. "EXECUTION_DRIFT_CRITICAL"
          "halt_recommended":   bool,
        }

    Insufficient data (< _ROLLING_WINDOW reconcilable trades) → rolling stats
    are None and `halt_recommended` is False. We never recommend halt on
    fewer than `_ROLLING_WINDOW` samples; the noise band isn't trustworthy
    yet.
    """
    per_trade: List[Dict[str, Any]] = []
    drift_arr: List[float] = []

    for t in trades or []:
        exp = _safe_float(t.get("expected_pnl_pct"))
        real = _safe_float(t.get("realized_pnl_pct"))
        if exp is None or real is None:
            continue
        d = real - exp
        per_trade.append({
            "expected_pnl_pct": exp,
            "realized_pnl_pct": real,
            "drift":            float(d),
            "exit_ts_ms":       t.get("exit_ts_ms"),
        })
        drift_arr.append(float(d))

    n = len(drift_arr)
    if n == 0:
        return {
            "n_trades":          0,
            "drift_series":      [],
            "rolling_window":    _ROLLING_WINDOW,
            "current_drift":     None,
            "rolling_mean":      None,
            "rolling_std":       None,
            "current_z":         None,
            "alert":             None,
            "halt_recommended":  False,
        }

    current_drift = float(drift_arr[-1])

    if n < _ROLLING_WINDOW:
        return {
            "n_trades":          n,
            "drift_series":      per_trade,
            "rolling_window":    _ROLLING_WINDOW,
            "current_drift":     current_drift,
            "rolling_mean":      None,
            "rolling_std":       None,
            "current_z":         None,
            "alert":             None,
            "halt_recommended":  False,
        }

    window = np.asarray(drift_arr[-_ROLLING_WINDOW:], dtype=np.float64)
    rolling_mean = float(window.mean())
    rolling_std = float(window.std(ddof=1)) if window.size > 1 else 0.0

    if rolling_std > 1e-12:
        current_z = (current_drift - rolling_mean) / rolling_std
    else:
        current_z = None

    # Halt only on NEGATIVE drift (we're paying away expected edge).
    halt_recommended = (
        current_z is not None and current_z <= -_HALT_SIGMA_THRESHOLD
    )
    alert = "EXECUTION_DRIFT_CRITICAL" if halt_recommended else None

    return {
        "n_trades":          n,
        "drift_series":      per_trade,
        "rolling_window":    _ROLLING_WINDOW,
        "current_drift":     current_drift,
        "rolling_mean":      round(rolling_mean, 6),
        "rolling_std":       round(rolling_std, 6),
        "current_z":         (round(float(current_z), 4) if current_z is not None else None),
        "alert":             alert,
        "halt_recommended":  bool(halt_recommended),
    }
