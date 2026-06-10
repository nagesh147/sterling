"""Full-cycle stress test: run the EXACT conviction book over 2020-now and read
out its per-year (regime) behaviour. Reuses study.regime_book unchanged. Reproducer
for docs/fullcycle_stress_test.md. Needs data/ohlcv_full (regenerate with:
study.ohlcv_pipeline --start 2020-01-01 --coins BTC ETH SOL --data-dir data/ohlcv_full).
Run: cd backend && .venv/bin/python -m study.fullcycle_stress"""
from __future__ import annotations

import numpy as np
import pandas as pd

from study.ohlcv_pipeline import load_universe
from study.regime_book import (
    select_conviction_book, split_sleeved_book, portfolio_equity_sized, _spearman,
)

COINS = ("BTC", "ETH", "SOL")
uni = load_universe("4h", data_dir="data/ohlcv_full")
frames = {f"{c}USD": uni[f"{c}USD"] for c in COINS if f"{c}USD" in uni}

# Full date span + the IS/OOS split point (oos_start=0.5 per symbol).
for sym, df in frames.items():
    t0, t1 = df.index[0], df.index[-1]
    cut = t0 + (t1 - t0) * 0.5
    print(f"{sym}: {t0.date()} -> {t1.date()}  | OOS starts {cut.date()}  ({len(df)} bars)")

# ── Full-cycle conviction book (IS-selected, OOS reported, deflated by 36) ──
sel = select_conviction_book(frames)
c = sel["chosen"]
o = c["oos"]
is_oos_corr = _spearman([s["is_sharpe"] for s in sel["scored"]],
                        [s["oos"]["sharpe"] for s in sel["scored"]])
wgmean = float(np.mean([s["oos"]["sharpe"] for s in sel["scored"]]))
print("\n=== FULL-CYCLE conviction book (2020-now) ===")
print(f"IS-best params (adx,rsi_lo,rsi_hi): {c['params']}")
print(f"OOS  return {o['ret']*100:+.1f}%  Sharpe {o['sharpe']:.2f}  maxDD {o['max_dd']*100:.1f}%  n={o['n']}")
print(f"DSR(grid=36): {sel['dsr']:.4f}   IS->OOS Spearman: {is_oos_corr:+.2f}   whole-grid OOS Sharpe mean: {wgmean:+.2f}")

# ── Per-year (regime) readout for the CHOSEN params over the FULL history ──
adx, lo, hi = c["params"]
is_t, oos_t = split_sleeved_book(frames, adx, lo, hi, oos_start=0.5)
all_t = is_t + oos_t

# basket (BTC/ETH/SOL equal-weight) yearly return = regime context
def basket_year_ret(year):
    rets = []
    for sym, df in frames.items():
        sub = df["close"][df.index.year == year]
        if len(sub) > 1:
            rets.append(sub.iloc[-1] / sub.iloc[0] - 1.0)
    return float(np.mean(rets)) if rets else float("nan")

print("\n=== Per-year regime readout (chosen params, full history) ===")
print(f"{'year':>6} {'book_ret':>9} {'sharpe':>7} {'n':>4} {'maxDD':>7}   {'basket(HODL)':>12}")
years = sorted({t["exit_time"].year for t in all_t})
for y in years:
    yt = [t for t in all_t if t["exit_time"].year == y]
    e = portfolio_equity_sized(yt, 500.0, 0.015, 3.0, 3, 1.0)
    bh = basket_year_ret(y)
    print(f"{y:>6} {e['ret']*100:>8.1f}% {e['sharpe']:>7.2f} {e['n']:>4} {e['max_dd']*100:>6.1f}%   {bh*100:>11.1f}%")

# whole-book full-history compounded (context, not OOS)
full = portfolio_equity_sized(all_t, 500.0, 0.015, 3.0, 3, 1.0)
print(f"\nfull-history book: $500 -> ${full['end']:.0f} ({full['ret']*100:+.0f}%)  Sharpe {full['sharpe']:.2f}  n={full['n']}  maxDD {full['max_dd']*100:.1f}%")
