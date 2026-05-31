"""Robustness-gate the edge-discovery 'top configs' with CPCV (López de Prado).

The 270-config matrix is a select-the-best-of-N exercise → the #1 (MA Crossover
4h BTC, Sharpe 1.83) is the prime overfit suspect. This replays the SAME edge
strategies (app/engines/edge/strategies.py — the ones that produced those
numbers) but records entry/exit bar indices, then runs Combinatorial Purged
Cross-Validation (app/engines/analytics/cpcv.py) to report, per config:

  full_sharpe   — in-sample Sharpe on all trades (what the matrix reported)
  mean_train    — avg train-fold Sharpe across CPCV paths
  mean_test     — avg OOS (held-out) Sharpe — THE number that matters
  pbo           — probability of backtest overfitting (lower = more robust)
  defl_oos      — deflated OOS Sharpe (prob the OOS edge is real, >0.95 = strong)

A config whose mean_test collapses vs mean_train / full_sharpe is curve-fit.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from app.engines.edge.strategies import SIGNAL_FNS, resample
from app.engines.analytics.cpcv import calculate_pbo

FEE_RT = 0.001
MAX_HOLD = 200

# (label, symbol, strategy, atr_sl, atr_tp) — the analysis 'top configs' + controls.
CONFIGS = [
    ("MA Crossover 4h BTC Intraday  (THE WINNER)", "BTCUSD", "ma_crossover", 2.0, 3.5),
    ("Breakout    4h BTC Intraday",                "BTCUSD", "breakout",     2.0, 3.5),
    ("SMC FVG     4h ETH Scalping",                "ETHUSD", "smc",          1.0, 2.0),
    ("SMC FVG     4h SOL Aggressive",              "SOLUSD", "smc",          1.5, 4.5),
    ("MeanRev     4h BTC Intraday  (replay-winner)","BTCUSD","mean_reversion",2.0, 3.5),
]


def load_4h(symbol: str) -> pd.DataFrame:
    df = pd.read_parquet(f"vector_store_1m_{symbol}.parquet",
                         columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time").sort_index()
    return resample(df, "4h")


def simulate_idx(df: pd.DataFrame, signals: np.ndarray, sl_m: float, tp_m: float):
    """Long-only first-touch SL/TP replay → list of {pnl_pct, entry_bar, exit_bar}."""
    close = df["close"].to_numpy(float); high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float); atr = df["atr"].to_numpy(float)
    n = len(close); out = []
    sig_idx = np.flatnonzero(signals); sp = 0
    while sp < len(sig_idx):
        i = sig_idx[sp]; sp += 1
        if i >= n - 2 or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        entry = close[i]; sl = entry - sl_m * atr[i]; tp = entry + tp_m * atr[i]
        end = min(i + MAX_HOLD, n - 1); ex_p = close[end]; ex_i = end
        for j in range(i + 1, end + 1):
            if low[j] <= sl:
                ex_p = sl; ex_i = j; break
            if high[j] >= tp:
                ex_p = tp; ex_i = j; break
        out.append({"pnl_pct": (ex_p / entry) - 1.0 - FEE_RT,
                    "entry_bar": int(i), "exit_bar": int(ex_i)})
        while sp < len(sig_idx) and sig_idx[sp] <= ex_i:
            sp += 1
    return out


def sharpe(pnls):
    a = np.asarray(pnls, float)
    if a.size < 2 or a.std(ddof=1) == 0:
        return 0.0
    return float(np.sqrt(252) * a.mean() / a.std(ddof=1))


_cache = {}
print(f"{'config':<46}{'trades':>7}{'full_Sh':>9}{'mn_train':>9}{'mn_test':>9}{'PBO':>7}{'defl_oos':>9}")
print("-" * 96)
for label, sym, strat, sl, tp in CONFIGS:
    if sym not in _cache:
        _cache[sym] = load_4h(sym)
    df = _cache[sym]
    sigs = SIGNAL_FNS[strat](df)
    trades = simulate_idx(df, sigs, sl, tp)
    n = len(trades)
    if n < 12:
        print(f"{label:<46}{n:>7}   too few trades for CPCV")
        continue
    full = sharpe([t["pnl_pct"] for t in trades])
    holds = [t["exit_bar"] - t["entry_bar"] for t in trades]
    hb = max(1, int(np.median(holds)))
    r = calculate_pbo(trades, hold_bars=hb, n_groups=6, k_test=2, train_min_trades=10)
    defl = r["deflated_sharpe_oos"]
    defl_s = f"{defl:.3f}" if defl is not None else "n/a"
    print(f"{label:<46}{n:>7}{full:>9.2f}{r['mean_train_sharpe']:>9.2f}"
          f"{r['mean_test_sharpe']:>9.2f}{r['pbo']:>7.2f}{defl_s:>9}")
print("-" * 96)
print("Read: mean_test ≈ full_Sh and PBO low ⇒ robust. mean_test ≪ full_Sh or PBO high ⇒ overfit.")
