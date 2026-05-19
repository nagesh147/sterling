"""
Tier-B #11 — Strategy Decay Tracker.

Pure module — no DB, no I/O, no `time.time()`. Ingests a list of TradeRecord-
shaped dicts (the truthful TTACE metrics path, so `net_pnl_pct` is the
post-cost return) and detects when a live/paper strategy is decaying so the
caller can auto-halt before drawdown compounds.

Algorithm:

  1. Drop trades missing `exit_ts_ms` or `net_pnl_pct`.
  2. Bucket trade `net_pnl_pct` into calendar-daily returns (sum per UTC day
     via `Series.resample('1D').sum()`). Idle days are filled with 0.0 so
     they correctly drag down a rolling-window Sharpe — that is the point
     of a decay monitor.
  3. Rolling 90-day Sharpe annualised by `sqrt(365)` (crypto trades 24/7).
  4. Flag decay when:
        - current_90d_sharpe < 0, OR
        - current_90d_sharpe < (1 - decay_drawdown_pct/100) * peak_90d_sharpe.

The peak is taken over the in-sample history of the rolling Sharpe series,
not the wall clock — pure-function friendly and reproducible across runs.

Designed to be called from a scheduled job that already has a `TradeRecord`
list materialised. Returns plain Python primitives so the report can be
serialised straight to JSON / pushed to alerts.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


_DAYS_PER_YEAR = 365.0
_ANNUALISER = math.sqrt(_DAYS_PER_YEAR)


@dataclass
class DecayReport:
    n_trades: int
    n_days: int
    current_90d_sharpe: Optional[float]
    peak_90d_sharpe: Optional[float]
    drawdown_from_peak_pct: Optional[float]
    decay_flag: bool
    reason: str = ""


def _coerce_trades(trades: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop trades missing the timestamp or truthful net-PnL field."""
    out: List[Dict[str, Any]] = []
    for t in trades:
        ts = t.get("exit_ts_ms")
        pnl = t.get("net_pnl_pct")
        if ts is None or pnl is None:
            continue
        out.append(t)
    return out


def track_decay(
    trades: Iterable[Dict[str, Any]],
    *,
    window_days: int = 90,
    decay_drawdown_pct: float = 50.0,
) -> DecayReport:
    """
    Compute a rolling 90-day Sharpe and flag strategy decay.

    Parameters
    ----------
    trades :
        Iterable of TradeRecord-shaped dicts. Each dict must carry
        `exit_ts_ms` (int, UTC ms) and `net_pnl_pct` (float, post-cost
        return on the closed slice of capital — the truthful TTACE field,
        NOT the gross `pnl_pct` legacy field).
    window_days :
        Rolling window for the Sharpe — default 90 calendar days.
    decay_drawdown_pct :
        Threshold for the "current dropped X% from peak" branch of the
        decay flag — default 50%.

    Returns
    -------
    DecayReport with:
      * `current_90d_sharpe`     — most recent rolling Sharpe (None until
                                    enough history accumulates).
      * `peak_90d_sharpe`        — historical max of the rolling Sharpe.
      * `drawdown_from_peak_pct` — (peak - current) / peak * 100; clamped
                                    to 0 when peak is non-positive.
      * `decay_flag`             — True when Sharpe has gone negative or
                                    dropped > `decay_drawdown_pct` from peak.

    All branches are deterministic functions of the input — no DB, no
    wall-clock reads.
    """
    items = _coerce_trades(trades)
    if not items:
        return DecayReport(
            n_trades=0, n_days=0,
            current_90d_sharpe=None, peak_90d_sharpe=None,
            drawdown_from_peak_pct=None, decay_flag=False,
            reason="no_trades",
        )

    ts = pd.to_datetime(
        [int(t["exit_ts_ms"]) for t in items], unit="ms", utc=True,
    )
    pnl = np.array([float(t["net_pnl_pct"]) for t in items], dtype=np.float64)
    series = pd.Series(pnl, index=ts).sort_index()

    # Daily returns: sum of per-trade net_pnl_pct bucketed into UTC days.
    # Resample("1D") fills empty days with 0.0 so idle stretches correctly
    # tighten the rolling-Sharpe distribution.
    daily = series.resample("1D").sum()
    n_days = int(daily.shape[0])

    if n_days < window_days:
        return DecayReport(
            n_trades=len(items), n_days=n_days,
            current_90d_sharpe=None, peak_90d_sharpe=None,
            drawdown_from_peak_pct=None, decay_flag=False,
            reason=f"insufficient_history:{n_days}<{window_days}",
        )

    mean = daily.rolling(window_days).mean()
    std = daily.rolling(window_days).std(ddof=1)
    rolling_sharpe = (mean / std * _ANNUALISER).replace(
        [np.inf, -np.inf], np.nan,
    ).dropna()

    if rolling_sharpe.empty:
        return DecayReport(
            n_trades=len(items), n_days=n_days,
            current_90d_sharpe=None, peak_90d_sharpe=None,
            drawdown_from_peak_pct=None, decay_flag=False,
            reason="degenerate_rolling_std",
        )

    current = float(rolling_sharpe.iloc[-1])
    peak = float(rolling_sharpe.max())

    if peak > 0:
        dd_pct = (peak - current) / peak * 100.0
    else:
        dd_pct = 0.0

    flag = False
    reason = ""
    if current < 0:
        flag = True
        reason = f"sharpe_below_zero:{current:.3f}"
    elif peak > 0 and dd_pct > decay_drawdown_pct:
        flag = True
        reason = (
            f"sharpe_decay:current={current:.3f}_peak={peak:.3f}_dd={dd_pct:.1f}%"
        )

    return DecayReport(
        n_trades=len(items), n_days=n_days,
        current_90d_sharpe=round(current, 4),
        peak_90d_sharpe=round(peak, 4),
        drawdown_from_peak_pct=round(dd_pct, 2),
        decay_flag=flag,
        reason=reason,
    )


def track_decay_dict(
    trades: Iterable[Dict[str, Any]],
    **kwargs: Any,
) -> Dict[str, Any]:
    """JSON-serialisable wrapper around `track_decay`."""
    r = track_decay(trades, **kwargs)
    return {
        "n_trades":               r.n_trades,
        "n_days":                 r.n_days,
        "current_90d_sharpe":     r.current_90d_sharpe,
        "peak_90d_sharpe":        r.peak_90d_sharpe,
        "drawdown_from_peak_pct": r.drawdown_from_peak_pct,
        "decay_flag":             r.decay_flag,
        "reason":                 r.reason,
    }
