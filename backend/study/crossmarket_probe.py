"""Cross-market test: does the EXACT conviction book work on UNCORRELATED markets
(Indian indices), and does pooling crypto + Indian lift the deflated Sharpe toward
the 0.5 provability bar? Reuses study.regime_book unchanged. Reproducer for
docs/crossmarket_result.md.

Needs data/ohlcv_full (crypto, study.ohlcv_pipeline --start 2020-01-01 --data-dir
data/ohlcv_full) and data/equity (study.equity_pipeline). Run:
cd backend && .venv/bin/python -m study.crossmarket_probe
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from study.ohlcv_pipeline import load_universe
from study.regime_book import select_conviction_book, split_sleeved_book, _spearman
from study.sim import sharpe as _sharpe
from app.engines.edge.robustness import deflated_sharpe_ratio


def run_book(frames, label):
    sel = select_conviction_book(frames)
    c = sel["chosen"]; o = c["oos"]
    corr = _spearman([s["is_sharpe"] for s in sel["scored"]],
                     [s["oos"]["sharpe"] for s in sel["scored"]])
    print(f"{label:>22}  params={c['params']}  OOS {o['ret']*100:+7.1f}%  "
          f"Sharpe {o['sharpe']:5.2f}  n={o['n']:>4}  DSR={sel['dsr']:.3f}  IS->OOS={corr:+.2f}")
    return sel


def oos_daily_returns(frames, chosen_params, oos_start=0.5):
    """Per-day realized pnl of the chosen book's OOS trades (raw pnl bucketed on
    exit day). The basis for cross-market correlation + diversification."""
    adx, lo, hi = chosen_params
    _, oos_t = split_sleeved_book(frames, adx, lo, hi, oos_start=oos_start)
    if not oos_t:
        return pd.Series(dtype="float64")
    s = {}
    for t in oos_t:
        d = pd.Timestamp(t["exit_time"]).normalize()
        s[d] = s.get(d, 0.0) + t["pnl_pct"]
    return pd.Series(s).sort_index()


# ── Standalone books (per-trade DSR, directly comparable across markets) ──
print("=== Standalone conviction book per market (same engine, unchanged) ===")
crypto = {k: v for k, v in load_universe("4h", data_dir="data/ohlcv_full").items()
          if k in ("BTCUSD", "ETHUSD", "SOLUSD")}
equity = load_universe("1d", data_dir="data/equity")
nifty = {"NIFTY": equity["NIFTY"]}
banknifty = {"BANKNIFTY": equity["BANKNIFTY"]}

sel_c = run_book(crypto, "CRYPTO (BTC/ETH/SOL)")
sel_n = run_book(nifty, "NIFTY")
sel_b = run_book(banknifty, "BANKNIFTY")
sel_ind = run_book(equity, "INDIAN (NIFTY+BANK)")

# ── Independence: correlation of the daily OOS return streams ──
rc = oos_daily_returns(crypto, sel_c["chosen"]["params"])
rn = oos_daily_returns(nifty, sel_n["chosen"]["params"])
rb = oos_daily_returns(banknifty, sel_b["chosen"]["params"])
idx = rc.index.union(rn.index).union(rb.index)
RC, RN, RB = (r.reindex(idx).fillna(0.0) for r in (rc, rn, rb))
print("\n=== Cross-market correlation of daily OOS returns (independence) ===")
M = pd.DataFrame({"crypto": RC, "nifty": RN, "banknifty": RB})
print(M.corr().round(3).to_string())

# ── Diversification: combined equal-weight daily portfolio vs crypto-alone ──
def daily_dsr(series, trials):
    a = series[series != 0.0].to_numpy()    # realized-day returns
    return deflated_sharpe_ratio(list(a), num_trials=trials), _sharpe(list(a))

combined = (RC + RN + RB) / 3.0
c_dsr, c_sh = daily_dsr(RC, 36)
k_dsr, k_sh = daily_dsr(combined, 36 * 3)   # 3 markets searched -> conservative 108 trials
print("\n=== Diversification (per-DAY basis; the right basis for pooling) ===")
print(f"  crypto-alone      daily-Sharpe {c_sh:5.2f}  DSR(36)  {c_dsr:.3f}")
print(f"  crypto+NIFTY+BANK daily-Sharpe {k_sh:5.2f}  DSR(108) {k_dsr:.3f}   <- pooled")
print(f"\n  >>> 0.5 provability bar: {'CLEARED' if k_dsr >= 0.5 else 'still below'} "
      f"(combined DSR {k_dsr:.3f})")
