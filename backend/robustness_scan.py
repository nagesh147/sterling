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
import sys
import time

import numpy as np
import pandas as pd

from app.engines.edge.strategies import SIGNAL_FNS, resample
from app.engines.analytics.cpcv import calculate_pbo
from app.engines.analytics.monte_carlo import monte_carlo_trades

FEE_RT = 0.001
MAX_HOLD = 200

SYMBOLS = ["BTCUSD", "ETHUSD", "SOLUSD"]
# Skip 1m/5m: pure fee-death (matrix already shows ~-100%) and they explode CPCV
# trade counts. The edge, if any, lives at >=15m.
TIMEFRAMES = [("15min", "15m"), ("30min", "30m"), ("1h", "1h"),
              ("2h", "2h"), ("4h", "4h")]
STRATEGIES = ["ma_crossover", "mean_reversion", "breakout", "price_action", "smc"]
PROFILES = {"Scalping": (1.0, 2.0), "Intraday": (2.0, 3.5), "Aggressive": (1.5, 4.5)}

# Survival gate
MIN_TRADES = 20
MAX_P_LOSS = 0.35          # reject configs that lose >35% of bootstrap paths
N_MC = 3000


def simulate_idx(df, sigs, slm, tpm):
    close = df["close"].to_numpy(float); high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float); atr = df["atr"].to_numpy(float); n = len(close)
    out = []; idx = np.flatnonzero(sigs); sp = 0
    while sp < len(idx):
        i = idx[sp]; sp += 1
        if i >= n - 2 or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        e = close[i]; sl = e - slm * atr[i]; tp = e + tpm * atr[i]
        end = min(i + MAX_HOLD, n - 1); xp = close[end]; xi = end
        for j in range(i + 1, end + 1):
            if low[j] <= sl: xp = sl; xi = j; break
            if high[j] >= tp: xp = tp; xi = j; break
        out.append({"pnl_pct": (xp / e) - 1.0 - FEE_RT, "entry_bar": int(i), "exit_bar": int(xi)})
        while sp < len(idx) and idx[sp] <= xi:
            sp += 1
    return out


def sharpe(pnls):
    a = np.asarray(pnls, float)
    return float(np.sqrt(252) * a.mean() / a.std(ddof=1)) if a.size >= 2 and a.std(ddof=1) > 0 else 0.0


def base_metrics(pnls):
    """win_rate, pf, expectancy, net_return(decimal), pnl_usd, max_dd(decimal)."""
    a = np.asarray(pnls, float)
    wins = a[a > 0]; losses = a[a < 0]
    gp = float(wins.sum()); gl = float(-losses.sum())
    pf = gp / gl if gl > 0 else (99.99 if gp > 0 else 0.0)
    win_rate = float((a > 0).mean())
    expectancy = float(a.mean())
    eq = np.cumprod(1.0 + a)
    net_return = float(eq[-1] - 1.0)
    peak = np.maximum.accumulate(eq)
    max_dd = float(((eq - peak) / peak).min())
    return win_rate, pf, expectancy, net_return, 500.0 * net_return, max_dd


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
                    rows.append({
                        # registry schema (load_edge_registry reads these) ──────
                        "symbol": sym, "tf": tf, "strategy": strat, "profile": prof,
                        "trades": n, "win_rate": round(win_rate, 4), "pf": round(pf, 4),
                        "sharpe": round(full_sh, 4), "expectancy": round(expectancy, 6),
                        "net_return": round(net_return, 6), "pnl_usd": round(pnl_usd, 2),
                        "max_dd": round(max_dd, 4),
                        "oos_sharpe": round(cp["mean_test_sharpe"], 4),
                        "p_loss": round(mc.prob_loss, 4),
                        # display-only extras ──────────────────────────────────
                        "ret%": round(net_return * 100, 1), "oos_keep": round(oos_keep, 2),
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
    # Survival gate: net-positive AND positive OOS Sharpe AND P(loss) under gate.
    # Use the exact p_loss (not the rounded %) so this count matches what the
    # live EdgeGate admits from the CSV.
    surv = res[(res["ret%"] > 0) & (res["oos_sharpe"] > 0) & (res["p_loss"] <= MAX_P_LOSS)]
    surv = surv.sort_values("oos_sharpe", ascending=False)

    print(f"\n=== {len(res)} configs evaluated · {len(surv)} survive the robustness gate ===")
    print("(gate: net>0, OOS Sharpe>0, P(loss)<=35%) · ranked by OOS Sharpe\n")
    hdr = f"{'config':<34}{'trd':>5}{'ret%':>8}{'full_Sh':>8}{'oos_Sh':>8}{'keep':>6}{'mc_ret_p05':>11}{'mc_dd_p05':>10}{'P_loss':>8}"
    print(hdr); print("-" * len(hdr))
    for _, r in surv.head(25).iterrows():
        print(f"{r['config']:<34}{r['trades']:>5}{r['ret%']:>8}{r['sharpe']:>8.2f}"
              f"{r['oos_sharpe']:>8.2f}{r['oos_keep']:>6}{r['mc_ret_p05']:>11}{r['mc_dd_p05']:>10}{r['P_loss%']:>7.0f}%")
    print(f"\n[csv] robustness_scan_results.csv · {time.time()-t0:.0f}s total")


if __name__ == "__main__":
    main()
