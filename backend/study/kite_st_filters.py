"""Phase-0c: ADX + ATR entry quality filter sweep.

Tests whether filtering entries by a minimum ADX (trend strength) or minimum
ATR percentile (volatility floor) improves the delta-1 baseline. These are the
candidate entry gates for directional mode.

The hypothesis: the triple-SuperTrend generates many false signals in choppy
(low-ADX) or compressed (low-ATR) regimes. An ADX floor ≥ 20 and/or ATR
percentile ≥ 50 should improve OOS profit factor and win rate.

Run:  python -m study.kite_st_filters
"""
from __future__ import annotations

import asyncio
import csv
import os
import warnings
from dataclasses import dataclass

import numpy as np

from app.engines.indicators.adx import adx as calc_adx_array
from app.engines.indicators.atr import atr_percentile, compute_atr
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.regime import compute_regime, entry_transitions
from study import kite_data

TRAIL_TARGET = "mid"
OOS_FRAC = 0.30
QTY = 50
STARTING_CAPITAL = 500_000.0
BARS_PER_DAY = 6.0

ADX_THRESHOLDS = [None, 15, 20, 25, 30]
ATR_THRESHOLDS = [None, 30, 50, 70]


@dataclass
class FilteredTrade:
    entry_ms: int; exit_ms: int; direction: str
    entry_price: float; exit_price: float
    net_pnl: float; bars_held: int


def replay_with_filters(*, o, h, l, c, ts, cfg, trail_target,
                         adx_min, atr_pct_min, qty, starting_capital):
    """Delta-1 replay with optional ADX/ATR entry filters."""
    n = len(c)
    trades: list = []
    if n <= cfg.warmup + 2:
        return trades

    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    trend = r.trend(trail_target)

    # Pre-compute ADX and ATR if filters are active
    adx_arr = None
    if adx_min is not None:
        adx_arr = calc_adx_array(
            np.asarray(h, dtype=float),
            np.asarray(l, dtype=float),
            np.asarray(c, dtype=float),
            period=14)

    atr_arr = None
    if atr_pct_min is not None:
        atr_arr = compute_atr(
            np.asarray(h, dtype=float),
            np.asarray(l, dtype=float),
            np.asarray(c, dtype=float),
            period=14)

    i = 0
    while i < n:
        is_long, is_short = bool(longs[i]), bool(shorts[i])
        if not (is_long or is_short):
            i += 1
            continue

        # Apply filters
        if adx_min is not None and adx_arr is not None and adx_arr[i] < adx_min:
            i += 1
            continue
        if atr_pct_min is not None and atr_arr is not None:
            pct = atr_percentile(atr_arr[:i + 1])
            if pct < atr_pct_min:
                i += 1
                continue

        want = 1 if is_long else -1
        sign = 1.0 if is_long else -1.0
        entry = float(c[i])

        exit_i = n - 1
        for j in range(i + 1, n):
            if int(trend[j]) != want:
                exit_i = j
                break

        exit_px = float(c[exit_i])
        gross = (exit_px - entry) * sign * qty
        trades.append(FilteredTrade(
            entry_ms=int(ts[i]), exit_ms=int(ts[exit_i]),
            direction="long" if is_long else "short",
            entry_price=entry, exit_price=exit_px,
            net_pnl=round(gross, 2), bars_held=exit_i - i))
        i = exit_i + 1

    return trades


def _stats(trades, capital):
    if not trades:
        return {"trades": 0, "win_rate": 0, "ret_pct": 0, "pf": 0}
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    net = sum(t.net_pnl for t in trades)
    gw = sum(t.net_pnl for t in wins) if wins else 0
    gl = abs(sum(t.net_pnl for t in losses)) if losses else 1e-9
    return {
        "trades": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "ret_pct": round(net / capital * 100, 1),
        "pf": round(gw / gl, 2) if gl else 0,
    }


def run_filter_sweep(data: dict) -> list:
    rows = []
    cfg = TripleSupertrendConfig(trail_target=TRAIL_TARGET)
    for name, arrs in data.items():
        n = len(arrs["c"])
        oos_lo = int(n * (1 - OOS_FRAC))
        full = {k: arrs[k] for k in ("o", "h", "l", "c", "ts")}
        oos_seg = {k: arrs[k][oos_lo:n] for k in ("o", "h", "l", "c", "ts")}

        for adx in ADX_THRESHOLDS:
            for atr in ATR_THRESHOLDS:
                common = dict(cfg=cfg, trail_target=TRAIL_TARGET,
                              adx_min=adx, atr_pct_min=atr,
                              qty=QTY, starting_capital=STARTING_CAPITAL)
                tf = replay_with_filters(**full, **common)
                to = replay_with_filters(**oos_seg, **common)
                sf = _stats(tf, STARTING_CAPITAL)
                so = _stats(to, STARTING_CAPITAL)
                rows.append({
                    "underlying": name,
                    "adx_min": adx or "off",
                    "atr_pct_min": atr or "off",
                    **{f"full_{k}": v for k, v in sf.items()},
                    **{f"oos_{k}": v for k, v in so.items()},
                })
    return rows


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    data = asyncio.run(kite_data.fetch_all())
    combos = len(ADX_THRESHOLDS) * len(ATR_THRESHOLDS)
    print(f"Filter sweep: {combos} combos × {len(data)} indices")
    rows = run_filter_sweep(data)
    out = os.path.join(os.path.dirname(__file__), "kite_st_filters_results.csv")
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"{len(rows)} rows → {out}")

    # Best filter combo per index (by OOS PF)
    for name in sorted({r["underlying"] for r in rows}):
        subset = [r for r in rows if r["underlying"] == name]
        best = max(subset, key=lambda r: r["oos_pf"])
        print(f"  {name:<18} best: ADX≥{best['adx_min']} ATR≥{best['atr_pct_min']} "
              f"OOS PF={best['oos_pf']} WR={best['oos_win_rate']}% "
              f"n={best['oos_trades']}")
