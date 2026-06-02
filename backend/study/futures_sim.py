"""Futures simulation for the derivatives edge study.

Thin wrapper around study.sim.simulate_idx that adds short-side
support and the ATR-trailing exit (spec Component 3). All configs use
the same bar-by-bar core, so the simulator just maps GridConfig
fields to the shared simulator parameters.
"""
from __future__ import annotations

import logging

import numpy as np

from study.sim import simulate_idx, base_metrics

log = logging.getLogger(__name__)


def simulate_futures_config(
    df,                  # DataFrame with close, high, low, atr
    signals: np.ndarray, # boolean, same length as df
    sl_mult: float,
    tp_mult: float,
    direction: str = "long",
    fee_rt: float = 0.001,
    max_hold: int = 200,
) -> dict:
    """Simulate one (strategy × profile × direction) futures config.

    Returns {"trades": list[dict], "metrics": dict}.
    """
    trades = simulate_idx(
        df=df, sigs=signals, slm=sl_mult, tpm=tp_mult,
        direction=direction, fee_rt=fee_rt, max_hold=max_hold,
    )
    n = len(trades)
    if n == 0:
        return {
            "trades": [],
            "metrics": {
                "trades": 0, "win_rate": 0.0, "pf": 0.0,
                "sharpe": 0.0, "expectancy": 0.0,
                "net_return": 0.0, "pnl_usd": 0.0, "max_dd": 0.0,
            },
        }
    pnls = [t["pnl_pct"] for t in trades]
    m = base_metrics(pnls)
    from study.sim import sharpe
    m["sharpe"] = round(sharpe(pnls), 4)
    m["trades"] = n
    return {"trades": trades, "metrics": m}


# ── ATR trailing exit (spec Component 3) ──────────────────────────────

def simulate_futures_trailing(
    df,
    signals: np.ndarray,
    sl_mult: float,
    direction: str = "long",
    trail_atr_mult: float = 2.0,
    fee_rt: float = 0.001,
    max_hold: int = 200,
) -> dict:
    """Futures simulation with ATR-trailing stop (no fixed TP).

    Each trade enters, sets an initial SL from sl_mult, then trails
    a moving stop at trail_atr_mult * atr behind the best price seen
    so far. Exits when low ≤ trailing stop (long) or high ≥ trailing
    stop (short), or max_hold expires.
    """
    close = df["close"].to_numpy(float)
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    n = len(close)

    trades: list[dict] = []
    idx = np.flatnonzero(signals)
    sp = 0

    while sp < len(idx):
        i = int(idx[sp])
        sp += 1
        if i >= n - 2 or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue

        e = close[i]
        if direction == "short":
            trail = e + trail_atr_mult * atr[i]  # trail above (exit when price rises)
        else:
            trail = e - trail_atr_mult * atr[i]  # trail below (exit when price falls)

        end = min(i + max_hold, n - 1)
        xp = close[end]
        xi = end
        best = e

        for j in range(i + 1, end + 1):
            if direction == "short":
                best = min(best, low[j])
                trail = min(trail, best + trail_atr_mult * atr[j])
                if high[j] >= trail:
                    xp = trail; xi = j; break
            else:
                best = max(best, high[j])
                trail = max(trail, best - trail_atr_mult * atr[j])
                if low[j] <= trail:
                    xp = trail; xi = j; break

        trades.append({
            "pnl_pct": (xp / e) - 1.0 - fee_rt if direction == "long"
                       else (1.0 - xp / e) - fee_rt,
            "entry_bar": int(i),
            "exit_bar": int(xi),
        })

        while sp < len(idx) and idx[sp] <= xi:
            sp += 1

    n_t = len(trades)
    if n_t == 0:
        return {"trades": [], "metrics": {"trades": 0, "win_rate": 0.0, "pf": 0.0,
                "sharpe": 0.0, "expectancy": 0.0, "net_return": 0.0,
                "pnl_usd": 0.0, "max_dd": 0.0}}
    pnls = [t["pnl_pct"] for t in trades]
    m = base_metrics(pnls)
    from study.sim import sharpe
    m["sharpe"] = round(sharpe(pnls), 4)
    m["trades"] = n_t
    return {"trades": trades, "metrics": m}
