"""Permutation sweep of the Kite Sterling Kite Engine options strategy on REAL data.

Replays the SAME signal logic the live Kite engine uses (Heikin-Ashi triple
SuperTrend, fresh full-alignment entries, trail-flip exits, optional early-lock)
over 7+ years of REAL 1H index candles, and sweeps every combination of the
strategy's knobs:

    underlying     × NIFTY 50 / NIFTY BANK / NIFTY FIN SERVICE / SENSEX
    trail_target   × fast / mid / slow
    early_lock     × off / on@0.5R / on@1.0R / on@1.5R   (faithfully modelled)
    moneyness      × ITM2 / ITM1 / ATM / OTM1 / OTM2

Each permutation is scored on the FULL history and on an IS(70%)/OOS(30%) split
so over-fit configs are exposed. Option premium is Black-Scholes-modelled (the
only way to test the signal over real history — expired strikes have no fetchable
premium), with the app's real Indian F&O cost schedule applied. The underlying
candles are REAL.

Reuses the app's own regime core, BS pricer, cost model and stats so results
match the production /kite/engine/backtest endpoint exactly.
"""
from __future__ import annotations

import csv
import os
from dataclasses import asdict
from datetime import datetime

import numpy as np

from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions
from app.services.kite_engine.backtest import (
    BacktestTrade, OptionCosts, _stats_from_trades,
)
from app.services.kite_engine.greeks import bs_price
from study import kite_data

# ── sweep grid ────────────────────────────────────────────────────────────────
TRAIL_TARGETS = ["fast", "mid", "slow"]
LOCK_VARIANTS = [            # (label, early_lock, profit_r)
    ("off", False, 0.0),
    ("lock@0.5R", True, 0.5),
    ("lock@1.0R", True, 1.0),
    ("lock@1.5R", True, 1.5),
]
MONEYNESS_STEPS = [          # (label, signed steps: -ITM .. +OTM)
    ("ITM2", -2), ("ITM1", -1), ("ATM", 0), ("OTM1", +1), ("OTM2", +2),
]

# fixed BS / contract assumptions (honest caveat in report).
# DTE=30 (monthly): the signal's median hold is ~3.7d and p90 ~10d, so a 7-DTE
# weekly would EXPIRE mid-trade — a monthly is the realistic expiry for this
# swing trend-follower. IV=0.18 is the app default (sensitivity reported).
IV = 0.18
DTE_DAYS = 30.0
QTY = 50
STARTING_CAPITAL = 100_000.0
BARS_PER_DAY = 6.0
OOS_FRAC = 0.30              # last 30% of bars held out


def replay(
    *, o, h, l, c, ts,
    cfg: SterlingKiteEngineConfig, trail_target: str,
    early_lock: bool, profit_r: float,
    moneyness_pct: float, iv: float, dte_days: float,
    qty: int, costs: OptionCosts, starting_capital: float,
) -> tuple:
    """Faithful synthetic replay. ST on the REAL underlying decides direction and
    entry; exit is the first of (a) trail_target flip, or (b) — when early_lock and
    underlying profit >= profit_r * initial risk — a SLOW-ST flip (mirrors
    engine.manage). Premium priced by BS at entry/exit. Returns (stats, trades)."""
    n = len(c)
    trades: list = []
    if n <= cfg.warmup + 2:
        return _stats_from_trades(trades, starting_capital)[0], trades

    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    trend = r.trend(trail_target)
    slow = r.trend("slow")
    line = r.line(trail_target)

    i = 0
    while i < n:
        is_long, is_short = bool(longs[i]), bool(shorts[i])
        if not (is_long or is_short):
            i += 1
            continue
        want = 1 if is_long else -1
        opt_type = "CE" if is_long else "PE"
        sign = 1.0 if is_long else -1.0
        spot0 = float(c[i])
        strike = round(spot0 * (1.0 + sign * moneyness_pct / 100.0), 0)
        initial_stop = float(line[i])
        risk = abs(spot0 - initial_stop) or 1e-9

        exit_i, reason = n - 1, "series end"
        for j in range(i + 1, n):
            if int(trend[j]) != want:                       # trail flip
                exit_i, reason = j, "trail flip"
                break
            if early_lock:                                  # early-lock slow-flip exit
                profit = (float(c[j]) - spot0) if is_long else (spot0 - float(c[j]))
                if profit >= profit_r * risk:
                    sflip = (int(slow[j]) == -1) if is_long else (int(slow[j]) == 1)
                    if sflip:
                        exit_i, reason = j, "early-lock"
                        break

        held = exit_i - i
        entry_dte = dte_days
        exit_dte = max(0.0, dte_days - held / max(BARS_PER_DAY, 1e-9))
        entry_px = bs_price(spot=spot0, strike=strike, dte_days=entry_dte, iv=iv, option_type=opt_type)
        exit_px = bs_price(spot=float(c[exit_i]), strike=strike, dte_days=exit_dte, iv=iv, option_type=opt_type)
        gross = (exit_px - entry_px) * qty
        ch = costs.round_trip(entry_px, exit_px, qty)
        trades.append(BacktestTrade(
            entry_ms=int(ts[i]), exit_ms=int(ts[exit_i]),
            direction="long-call" if is_long else "long-put",
            entry_premium=round(entry_px, 2), exit_premium=round(exit_px, 2), qty=qty,
            gross_pnl=round(gross, 2), costs=round(ch, 2), net_pnl=round(gross - ch, 2),
            bars_held=held, exit_reason=reason))
        i = exit_i + 1

    stats, _ = _stats_from_trades(trades, starting_capital)
    return stats, trades


def _slice(arrs, lo, hi):
    return {k: arrs[k][lo:hi] for k in ("o", "h", "l", "c", "ts")}


def run_grid(data: dict) -> list:
    """Sweep every permutation on full / IS / OOS for every index. Returns rows."""
    costs = OptionCosts()
    rows: list = []
    for name, arrs in data.items():
        median_spot = float(np.median(arrs["c"]))
        step = next(ix["strike_step"] for ix in kite_data.INDICES if ix["name"] == name)
        step_pct = step / median_spot * 100.0
        n = len(arrs["c"])
        oos_lo = int(n * (1 - OOS_FRAC))
        full = {k: arrs[k] for k in ("o", "h", "l", "c", "ts")}
        is_seg = _slice(arrs, 0, oos_lo)
        oos_seg = _slice(arrs, oos_lo, n)

        for tt in TRAIL_TARGETS:
            for lock_label, el, pr in LOCK_VARIANTS:
                cfg = SterlingKiteEngineConfig(trail_target=tt, early_lock=el, early_lock_profit_r=pr)
                for mny_label, steps in MONEYNESS_STEPS:
                    mny_pct = steps * step_pct
                    common = dict(cfg=cfg, trail_target=tt, early_lock=el, profit_r=pr,
                                  moneyness_pct=mny_pct, iv=IV, dte_days=DTE_DAYS,
                                  qty=QTY, costs=costs, starting_capital=STARTING_CAPITAL)
                    sf, _ = replay(**full, **common)
                    si, _ = replay(**is_seg, **common)
                    so, _ = replay(**oos_seg, **common)
                    rows.append({
                        "underlying": name, "trail": tt, "lock": lock_label,
                        "moneyness": mny_label, "moneyness_pct": round(mny_pct, 3),
                        "trades": sf.trades, "win_rate": round(sf.win_rate * 100, 1),
                        "ret_pct": sf.return_pct, "net_pnl": sf.net_pnl,
                        "profit_factor": sf.profit_factor, "sharpe": sf.sharpe,
                        "max_dd": sf.max_drawdown, "expectancy": sf.expectancy,
                        "is_ret": si.return_pct, "is_trades": si.trades, "is_pf": si.profit_factor,
                        "oos_ret": so.return_pct, "oos_trades": so.trades, "oos_pf": so.profit_factor,
                    })
    return rows


def sensitivity(data: dict, best: dict) -> dict:
    """IV and DTE sensitivity for one config (the global best), full history."""
    costs = OptionCosts()
    arrs = data[best["underlying"]]
    full = {k: arrs[k] for k in ("o", "h", "l", "c", "ts")}
    median_spot = float(np.median(arrs["c"]))
    step = next(ix["strike_step"] for ix in kite_data.INDICES if ix["name"] == best["underlying"])
    mny_pct = next(s for lbl, s in MONEYNESS_STEPS if lbl == best["moneyness"]) * step / median_spot * 100.0
    cfg = SterlingKiteEngineConfig(trail_target=best["trail"])
    base = dict(cfg=cfg, trail_target=best["trail"], early_lock=False, profit_r=0.0,
                moneyness_pct=mny_pct, qty=QTY, costs=costs, starting_capital=STARTING_CAPITAL)
    out = {"iv": [], "dte": []}
    for iv in (0.10, 0.14, 0.18, 0.22, 0.28):
        s, _ = replay(**full, **base, iv=iv, dte_days=DTE_DAYS)
        out["iv"].append({"iv": iv, "ret": s.return_pct, "pf": s.profit_factor, "sharpe": s.sharpe})
    for dte in (7.0, 14.0, 30.0, 45.0, 60.0):
        s, _ = replay(**full, **base, iv=IV, dte_days=dte)
        out["dte"].append({"dte": dte, "ret": s.return_pct, "pf": s.profit_factor, "sharpe": s.sharpe})
    return out


def is_oos_corr(rows: list) -> float:
    """Spearman rank corr between IS and OOS return across configs — a robustness
    proxy. Positive => configs that did well IS tend to do well OOS (signal, not
    overfit); <=0 => the ranking does not survive the holdout."""
    uniq = {}
    for r in rows:                       # collapse the inert lock dimension
        key = (r["underlying"], r["trail"], r["moneyness"])
        uniq[key] = r
    items = list(uniq.values())
    if len(items) < 3:
        return 0.0
    def rank(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        rk = [0] * len(vals)
        for pos, i in enumerate(order):
            rk[i] = pos
        return rk
    ri = rank([r["is_ret"] for r in items])
    ro = rank([r["oos_ret"] for r in items])
    n = len(items)
    d2 = sum((ri[i] - ro[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n * n - 1)), 3)


def write_csv(rows: list, path: str):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    import asyncio
    import warnings
    warnings.filterwarnings("ignore")
    data = asyncio.run(kite_data.fetch_all())
    print(f"\nSweeping {len(TRAIL_TARGETS)*len(LOCK_VARIANTS)*len(MONEYNESS_STEPS)} "
          f"permutations × {len(data)} indices × 3 windows ...")
    rows = run_grid(data)
    out_csv = os.path.join(os.path.dirname(__file__), "kite_st_sweep_results.csv")
    write_csv(rows, out_csv)
    print(f"{len(rows)} rows -> {out_csv}")

    corr = is_oos_corr(rows)
    print(f"\nIS->OOS Spearman rank corr (robustness): {corr}")

    # rank by OOS first (out-of-sample is the honest metric), then full
    top = sorted(rows, key=lambda r: r["oos_ret"], reverse=True)[:12]
    print("\nTop 12 by OOS return:")
    for r in top:
        print(f"  {r['underlying']:<18} {r['trail']:<4} {r['lock']:<9} {r['moneyness']:<4} "
              f"full={r['ret_pct']:>9.1f}%  IS={r['is_ret']:>9.1f}%  OOS={r['oos_ret']:>7.1f}%  "
              f"PF={r['profit_factor']}  oosPF={r['oos_pf']}  n={r['trades']}")

    # global best by OOS (lock=off representative), then its IV/DTE sensitivity
    best = max((r for r in rows if r["lock"] == "off"), key=lambda r: r["oos_ret"])
    print(f"\nGlobal best (by OOS): {best['underlying']} {best['trail']} {best['moneyness']}")
    sens = sensitivity(data, best)
    print("  IV sensitivity:", [(s["iv"], s["ret"], s["pf"]) for s in sens["iv"]])
    print("  DTE sensitivity:", [(s["dte"], s["ret"], s["pf"]) for s in sens["dte"]])

    import json
    with open(os.path.join(os.path.dirname(__file__), "kite_st_sweep_meta.json"), "w") as f:
        json.dump({"is_oos_corr": corr, "best": best, "sensitivity": sens}, f, indent=2)
