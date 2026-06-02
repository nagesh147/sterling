"""Shared bar-by-bar first-touch SL/TP simulator.

Extracted from robustness_scan.py so that the study modules AND the
existing robustness scanner share a single, tested implementation.

Both long and short directions are supported. The per-trade loop is
sequential (inevitable for first-touch logic with position overlap
avoidance) but the inner bar scan uses numpy array access.
"""
from __future__ import annotations

import numpy as np

FEE_RT = 0.001
MAX_HOLD = 200


def simulate_idx(
    df,          # DataFrame with columns: close, high, low, atr
    sigs,        # np.ndarray[bool], same length as df
    slm: float,  # stop-loss ATR multiplier
    tpm: float,  # take-profit ATR multiplier
    direction: str = "long",
    fee_rt: float = 0.001,
    max_hold: int = 200,
) -> list[dict]:
    """Bar-by-bar first-touch SL/TP simulator.

    For each signal bar, enters at close then walks forward until SL
    or TP is touched (or max_hold expires). Skips signals that would
    overlap an open position (sequential — no pyramiding).

    Long:  SL = entry - slm*atr below, TP = entry + tpm*atr above
    Short: SL = entry + slm*atr above, TP = entry - tpm*atr below

    Returns list of {"pnl_pct": float, "entry_bar": int, "exit_bar": int}.
    """
    close = df["close"].to_numpy(float)
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    n = len(close)

    out: list[dict] = []
    idx = np.flatnonzero(sigs)
    sp = 0

    while sp < len(idx):
        i = int(idx[sp])
        sp += 1

        # Must have at least 2 bars ahead and a valid ATR.
        if i >= n - 2 or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue

        e = close[i]

        if direction == "short":
            sl = e + slm * atr[i]   # SL above entry
            tp = e - tpm * atr[i]   # TP below entry
        else:
            sl = e - slm * atr[i]   # SL below entry
            tp = e + tpm * atr[i]   # TP above entry

        end = min(i + max_hold, n - 1)
        xp = close[end]
        xi = end

        for j in range(i + 1, end + 1):
            if direction == "short":
                if high[j] >= sl:
                    xp = sl; xi = j; break
                if low[j] <= tp:
                    xp = tp; xi = j; break
            else:
                if low[j] <= sl:
                    xp = sl; xi = j; break
                if high[j] >= tp:
                    xp = tp; xi = j; break

        out.append({
            "pnl_pct": (xp / e) - 1.0 - fee_rt if direction == "long"
                       else (1.0 - xp / e) - fee_rt,
            "entry_bar": int(i),
            "exit_bar": int(xi),
        })

        # Skip signals that fall within the open position.
        while sp < len(idx) and idx[sp] <= xi:
            sp += 1

    return out


def sharpe(pnls: list[float]) -> float:
    """Annualized Sharpe ratio (sqrt(252))."""
    a = np.asarray(pnls, float)
    if a.size >= 2:
        s = a.std(ddof=1)
        if s > 0:
            return float(np.sqrt(252) * a.mean() / s)
    return 0.0


def base_metrics(
    pnls: list[float],
    starting_capital: float = 500.0,
) -> dict:
    """Compute win_rate, pf, expectancy, net_return, pnl_usd, max_dd.

    Returns a dict suitable for CSV/DataFrame ingestion.
    """
    a = np.asarray(pnls, float)
    if a.size == 0:
        return {
            "win_rate": 0.0, "pf": 0.0, "expectancy": 0.0,
            "net_return": 0.0, "pnl_usd": 0.0, "max_dd": 0.0,
        }
    wins = a[a > 0]
    losses = a[a < 0]
    gp = float(wins.sum())
    gl = float(-losses.sum())
    pf = gp / gl if gl > 0 else (99.99 if gp > 0 else 0.0)
    win_rate = float((a > 0).mean())
    expectancy = float(a.mean())
    eq = np.cumprod(1.0 + a)
    net_return = float(eq[-1] - 1.0)
    peak = np.maximum.accumulate(eq)
    max_dd = float(((eq - peak) / peak).min())
    return {
        "win_rate": round(win_rate, 4),
        "pf": round(pf, 4),
        "expectancy": round(expectancy, 6),
        "net_return": round(net_return, 6),
        "pnl_usd": round(starting_capital * net_return, 2),
        "max_dd": round(max_dd, 4),
    }
