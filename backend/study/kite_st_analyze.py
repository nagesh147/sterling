"""Post-sweep analysis: best-per-index tables, a signal-isolation diagnostic
(would the SAME entries make money on the underlying / a delta-1 future, with the
options wrapper stripped out?), and aggregate stats for the report."""
from __future__ import annotations

import asyncio
import csv
import json
import os
import warnings

import numpy as np

warnings.filterwarnings("ignore")

from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions
from app.services.kite_engine.backtest import _stats_from_trades, BacktestTrade
from study import kite_data

HERE = os.path.dirname(__file__)


def underlying_signal_pnl(arrs, trail_target: str, lo=0, hi=None, cost_bps=3.0):
    """Strip the options wrapper: trade the UNDERLYING long on bull / short on bear,
    exit on trail flip. Isolates whether the SIGNAL itself has directional edge.
    cost_bps = round-trip friction (futures are cheap). Returns stats."""
    o, h, l, c, ts = (arrs[k][lo:hi] for k in ("o", "h", "l", "c", "ts"))
    cfg = SterlingKiteEngineConfig(trail_target=trail_target)
    n = len(c)
    trades = []
    if n <= cfg.warmup + 2:
        return _stats_from_trades(trades, 100_000.0)[0]
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    trend = r.trend(trail_target)
    i = 0
    while i < n:
        is_long, is_short = bool(longs[i]), bool(shorts[i])
        if not (is_long or is_short):
            i += 1
            continue
        want = 1 if is_long else -1
        entry = float(c[i])
        exit_i, reason = n - 1, "series end"
        for j in range(i + 1, n):
            if int(trend[j]) != want:
                exit_i, reason = j, "trail flip"
                break
        ex = float(c[exit_i])
        # pct move in the direction of the trade, minus round-trip friction
        move = (ex - entry) / entry if is_long else (entry - ex) / entry
        net = move - cost_bps / 1e4
        trades.append(BacktestTrade(
            entry_ms=int(ts[i]), exit_ms=int(ts[exit_i]),
            direction="long" if is_long else "short",
            entry_premium=round(entry, 2), exit_premium=round(ex, 2), qty=1,
            gross_pnl=round(move * 1e5, 2), costs=round(cost_bps / 1e4 * 1e5, 2),
            net_pnl=round(net * 1e5, 2), bars_held=exit_i - i, exit_reason=reason))
        i = exit_i + 1
    stats, _ = _stats_from_trades(trades, 100_000.0)
    return stats


def main():
    with open(os.path.join(HERE, "kite_st_sweep_results.csv")) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("ret_pct", "is_ret", "oos_ret", "profit_factor", "oos_pf", "sharpe",
                  "max_dd", "win_rate", "expectancy"):
            r[k] = float(r[k])
        for k in ("trades", "oos_trades", "is_trades"):
            r[k] = int(r[k])

    # collapse the inert lock dimension for ranking
    off = [r for r in rows if r["lock"] == "off"]

    print("=== BEST CONFIG PER INDEX (by OOS return, lock=off) ===")
    per_index = {}
    for name in sorted({r["underlying"] for r in off}):
        sub = [r for r in off if r["underlying"] == name]
        b = max(sub, key=lambda r: r["oos_ret"])
        per_index[name] = b
        print(f"  {name:<18} trail={b['trail']:<4} mny={b['moneyness']:<4} "
              f"full={b['ret_pct']:>8.1f}%  IS={b['is_ret']:>8.1f}%  OOS={b['oos_ret']:>7.1f}%  "
              f"PF={b['profit_factor']}  oosPF={b['oos_pf']}  n={b['trades']}")

    print("\n=== AGGREGATES (lock=off, 60 configs) ===")
    full_pos = sum(1 for r in off if r["ret_pct"] > 0)
    oos_pos = sum(1 for r in off if r["oos_ret"] > 0)
    oos_pf_pos = sum(1 for r in off if r["oos_pf"] > 1.0)
    print(f"  full-history net-positive: {full_pos}/{len(off)}")
    print(f"  OOS net-positive:          {oos_pos}/{len(off)}")
    print(f"  OOS profit-factor > 1.0:   {oos_pf_pos}/{len(off)}")
    print(f"  best full ret: {max(r['ret_pct'] for r in off):.1f}%   "
          f"best OOS ret: {max(r['oos_ret'] for r in off):.1f}%")

    # effect of trail target and moneyness (mean OOS)
    print("\n=== MEAN OOS RETURN by knob ===")
    for dim in ("trail", "moneyness"):
        agg = {}
        for r in off:
            agg.setdefault(r[dim], []).append(r["oos_ret"])
        print(f"  {dim}: " + "  ".join(f"{k}={np.mean(v):+.1f}%" for k, v in agg.items()))

    # signal-isolation diagnostic
    print("\n=== SIGNAL-ISOLATION: underlying (delta-1) P&L on the SAME signals ===")
    print("    (strips IV/theta — does the ST entry have directional edge at all?)")
    data = asyncio.run(kite_data.fetch_all())
    sig = {}
    for name, arrs in data.items():
        n = len(arrs["c"]); oos_lo = int(n * 0.7)
        row = {}
        for tt in ("fast", "mid", "slow"):
            sf = underlying_signal_pnl(arrs, tt)
            so = underlying_signal_pnl(arrs, tt, lo=oos_lo)
            row[tt] = {"full_ret": sf.return_pct, "full_pf": sf.profit_factor,
                       "full_wr": round(sf.win_rate * 100, 1), "n": sf.trades,
                       "oos_ret": so.return_pct, "oos_pf": so.profit_factor}
        sig[name] = row
        best_tt = max(row, key=lambda t: row[t]["full_pf"])
        b = row[best_tt]
        print(f"  {name:<18} best trail={best_tt:<4} full ret={b['full_ret']:>7.1f}% "
              f"PF={b['full_pf']} WR={b['full_wr']}%  | OOS ret={b['oos_ret']:>7.1f}% PF={b['oos_pf']}  n={b['n']}")

    with open(os.path.join(HERE, "kite_st_analysis.json"), "w") as f:
        json.dump({"per_index_best": per_index,
                   "aggregates": {"full_pos": full_pos, "oos_pos": oos_pos,
                                  "oos_pf_pos": oos_pf_pos, "n": len(off)},
                   "signal_isolation": sig}, f, indent=2, default=str)
    print("\nwrote kite_st_analysis.json")


if __name__ == "__main__":
    main()
