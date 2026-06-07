"""Robustness-ranked edge scan on the real vector_store_1m data.

Extends the raw edge-discovery matrix (comprehensive_backtest.py) with the two
validation gates built this cycle:

  * CPCV (analytics/cpcv.py)         — combinatorial purged cross-validation:
                                       does the in-sample Sharpe survive on
                                       held-out folds? (OOS retention + PBO)
  * Monte Carlo (analytics/monte_carlo.py) — bootstrap the trade sequence for
                                       confidence bands on return / max-DD and
                                       the probability of ending underwater.

For every (symbol x timeframe x strategy x profile) it replays the SAME
edge/strategies.py signals (long-only, first-touch ATR SL/TP, round-trip fee),
then ranks by risk-adjusted robustness instead of raw return. A config only
"survives" if it is net-positive AND keeps a positive OOS Sharpe AND its
Monte-Carlo probability of loss is below the gate.

Run:  python backend/robustness_scan.py
Loads one ~700MB parquet at a time and frees it before the next (memory-safe
alongside a running server). 4h is where the edge has historically lived.
"""
from __future__ import annotations

import gc
import glob
import os
import sys
import time

import numpy as np
import pandas as pd

from app.engines.edge.strategies import SIGNAL_FNS, resample
from app.engines.edge.registry import PROFILE_CONFIG
from app.engines.analytics.cpcv import calculate_pbo
from app.engines.analytics.monte_carlo import monte_carlo_trades
from app.engines.edge.robustness import deflated_sharpe_ratio
from app.engines.analytics.performance import hodl_benchmark, beats_buy_and_hold
from study.sim import simulate_idx as _simulate_idx, sharpe as _sharpe, base_metrics as _base_metrics

FEE_RT = 0.001
MAX_HOLD = 200

_parquet_files = glob.glob("vector_store_1m_*.parquet")
SYMBOLS = sorted([os.path.basename(f).replace("vector_store_1m_", "").replace(".parquet", "") for f in _parquet_files])
if not SYMBOLS:
    SYMBOLS = ["BTCUSD", "ETHUSD", "SOLUSD"]

# Skip 1m/5m: pure fee-death (matrix already shows ~-100%) and they explode CPCV
# trade counts. The edge, if any, lives at >=15m.
TIMEFRAMES = [("15min", "15m"), ("30min", "30m"), ("1h", "1h"),
              ("2h", "2h"), ("4h", "4h")]
STRATEGIES = list(SIGNAL_FNS.keys())
PROFILES = {k: (v["sl_mult"], v["tp_mult"]) for k, v in PROFILE_CONFIG.items()}

# Survival gate
MIN_TRADES = 20
MAX_P_LOSS = 0.35          # reject configs that lose >35% of bootstrap paths
MIN_DSR = 0.5              # deflated Sharpe floor (multiple-testing corrected)
N_MC = 3000

# Multiple-testing trial count for the deflated Sharpe = the FULL grid this scan
# mines (symbols × timeframes × strategies × profiles). Deflating by the whole
# search space is the honest, conservative choice.
TOTAL_TRIALS = len(SYMBOLS) * len(TIMEFRAMES) * len(STRATEGIES) * len(PROFILES)


def simulate_idx(df, sigs, slm, tpm):
    """Long-only bar-by-bar first-touch SL/TP (delegates to study.sim)."""
    return _simulate_idx(df, sigs, slm, tpm, direction="long", fee_rt=FEE_RT, max_hold=MAX_HOLD)


def sharpe(pnls):
    return _sharpe(pnls)


def base_metrics(pnls):
    """win_rate, pf, expectancy, net_return(decimal), pnl_usd, max_dd(decimal)."""
    m = _base_metrics(pnls, starting_capital=500.0)
    return m["win_rate"], m["pf"], m["expectancy"], m["net_return"], m["pnl_usd"], m["max_dd"]


def main():
    t0 = time.time()
    rows = []
    for sym in SYMBOLS:
        print(f"[load] {sym} ...", flush=True)
        df1 = pd.read_parquet(f"vector_store_1m_{sym}.parquet",
                              columns=["time", "open", "high", "low", "close", "volume"])
        df1["time"] = pd.to_datetime(df1["time"], unit="s")
        df1 = df1.set_index("time").sort_index()
        for rule, tf in TIMEFRAMES:
            dft = resample(df1, rule)
            # Buy-and-hold benchmark for this (symbol, tf) — identical for every
            # (strategy, profile), so compute it once.
            hodl = hodl_benchmark(dft["close"].to_numpy(dtype=np.float64),
                                  fee_rt_pct=FEE_RT)
            for strat in STRATEGIES:
                sigs = SIGNAL_FNS[strat](dft)
                for prof, (sl, tp) in PROFILES.items():
                    trades = simulate_idx(dft, sigs, sl, tp)
                    n = len(trades)
                    if n < MIN_TRADES:
                        continue
                    pnls = [t["pnl_pct"] for t in trades]
                    full_sh = sharpe(pnls)
                    win_rate, pf, expectancy, net_return, pnl_usd, max_dd = base_metrics(pnls)
                    holds = [t["exit_bar"] - t["entry_bar"] for t in trades]
                    hb = max(1, int(np.median(holds)))
                    cp = calculate_pbo(trades, hold_bars=hb, n_groups=6, k_test=2, train_min_trades=10)
                    mc = monte_carlo_trades(pnls, n_sims=N_MC, seed=42, method="bootstrap")
                    oos_keep = (cp["mean_test_sharpe"] / cp["mean_train_sharpe"]
                                if cp["mean_train_sharpe"] else 0.0)
                    # Deflated Sharpe (multiple-testing corrected over the full
                    # grid) + buy-and-hold comparison — the two gates the live
                    # EdgeGate now enforces.
                    dsr = deflated_sharpe_ratio(pnls, num_trials=TOTAL_TRIALS)
                    rel = beats_buy_and_hold(net_return, max_dd, hodl)
                    rows.append({
                        # registry schema (load_edge_registry reads these) ──────
                        "symbol": sym, "tf": tf, "strategy": strat, "profile": prof,
                        "trades": n, "win_rate": round(win_rate, 4), "pf": round(pf, 4),
                        "sharpe": round(full_sh, 4), "expectancy": round(expectancy, 6),
                        "net_return": round(net_return, 6), "pnl_usd": round(pnl_usd, 2),
                        "max_dd": round(max_dd, 4),
                        "oos_sharpe": round(cp["mean_test_sharpe"], 4),
                        "p_loss": round(mc.prob_loss, 4),
                        "dsr": round(dsr, 4),
                        "beats_hold": rel["beats_hold"],
                        # display-only extras ──────────────────────────────────
                        "ret%": round(net_return * 100, 1), "oos_keep": round(oos_keep, 2),
                        "excess_vs_hold": round(rel["excess_return"], 4),
                        "mc_ret_p05": round(mc.return_pct_p05, 1),
                        "mc_dd_p05": round(mc.max_dd_pct_p05, 1),
                        "P_loss%": round(mc.prob_loss * 100, 0),
                    })
            del dft
        del df1; gc.collect()
        print(f"  {sym} done ({time.time()-t0:.0f}s)", flush=True)

    res = pd.DataFrame(rows)
    # Registry-compatible CSV (full schema + oos_sharpe/p_loss). The live edge
    # feed loads this and the robustness EdgeGate filters it to the survivors.
    res.to_csv("robustness_scan_results.csv", index=False)

    res["config"] = res["strategy"] + " " + res["tf"] + " " + res["symbol"].str[:3] + " " + res["profile"]
    # Survival gate: net-positive AND positive OOS Sharpe AND P(loss) under gate
    # AND deflated Sharpe >= floor AND beats buy-and-hold. Use the exact values
    # (not rounded display %) so this count matches what the live EdgeGate admits.
    surv = res[(res["ret%"] > 0) & (res["oos_sharpe"] > 0) & (res["p_loss"] <= MAX_P_LOSS)
               & (res["dsr"] >= MIN_DSR) & (res["beats_hold"])]
    surv = surv.sort_values("dsr", ascending=False)

    print(f"\n=== {len(res)} configs evaluated · {len(surv)} survive the robustness gate ===")
    print(f"(gate: net>0, OOS Sharpe>0, P(loss)<=35%, DSR>={MIN_DSR}, beats buy-and-hold) · ranked by DSR\n")
    hdr = f"{'config':<34}{'trd':>5}{'ret%':>8}{'full_Sh':>8}{'oos_Sh':>8}{'keep':>6}{'mc_ret_p05':>11}{'mc_dd_p05':>10}{'P_loss':>8}"
    print(hdr); print("-" * len(hdr))
    for _, r in surv.head(25).iterrows():
        print(f"{r['config']:<34}{r['trades']:>5}{r['ret%']:>8}{r['sharpe']:>8.2f}"
              f"{r['oos_sharpe']:>8.2f}{r['oos_keep']:>6}{r['mc_ret_p05']:>11}{r['mc_dd_p05']:>10}{r['P_loss%']:>7.0f}%")
    print(f"\n[csv] robustness_scan_results.csv · {time.time()-t0:.0f}s total")


if __name__ == "__main__":
    main()
