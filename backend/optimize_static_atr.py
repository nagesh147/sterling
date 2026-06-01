import glob
import os
import sys
import numpy as np
import pandas as pd
from itertools import product

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.engines.edge.strategies import SIGNAL_FNS, resample
from comprehensive_backtest import metrics, STARTING_CAPITAL, FEE_ROUND_TRIP, MAX_HOLD_BARS

def simulate_static(df, signals, sl_mult, tp_mult):
    close = df["close"].to_numpy(dtype=np.float64)
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)
    atr = df["atr"].to_numpy(dtype=np.float64)
    n = len(close)
    trades = []
    sig_idx = np.flatnonzero(signals)
    sp = 0
    while sp < len(sig_idx):
        i = sig_idx[sp]
        sp += 1
        if i >= n - 2 or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        entry = close[i]
        sl = entry - sl_mult * atr[i]
        tp = entry + tp_mult * atr[i]
        end = min(i + MAX_HOLD_BARS, n - 1)
        exit_price = close[end]
        exit_idx = end
        for j in range(i + 1, end + 1):
            if low[j] <= sl:
                exit_price = sl
                exit_idx = j
                break
            if high[j] >= tp:
                exit_price = tp
                exit_idx = j
                break
        trades.append((exit_price / entry) - 1.0 - FEE_ROUND_TRIP)
        while sp < len(sig_idx) and sig_idx[sp] <= exit_idx:
            sp += 1
    return np.asarray(trades, dtype=np.float64)

def main():
    import glob
    files = glob.glob("/home/nageshmadaram/Sterling/backend/vector_store_1m_*.parquet")
    tf = "4h"
    strat_name = "ma_crossover"
    
    sl_mults = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    tp_mults = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
    
    for f in files:
        sym = f.split("_")[-1].split(".")[0]
        print(f"\n{'='*85}")
        print(f"Loading {sym} vector store...")
        df_1m = pd.read_parquet(f)
        df_1m["time"] = pd.to_datetime(df_1m["time"], unit="s")
        df_1m = df_1m.rename(columns={"volatility_atr": "atr"}).set_index("time").sort_index()
        
        df_tf = resample(df_1m, tf)
        sig_fn = SIGNAL_FNS[strat_name]
        signals = sig_fn(df_tf)
        
        results = []
        for sl, tp in product(sl_mults, tp_mults):
            returns = simulate_static(df_tf, signals, sl, tp)
            if len(returns) > 0:
                m = metrics(returns, tf)
                pnl_usd = m["end_capital"] - STARTING_CAPITAL
                results.append({
                    "SL": sl, "TP": tp, "Trades": m["trades"], "WinRate": m["win_rate"], 
                    "ProfitFactor": m["pf"], "MaxDD": m["max_dd"], "Sharpe": m["sharpe"], "PnL": pnl_usd
                })
                
        results.sort(key=lambda x: x["PnL"], reverse=True)
        
        print(f"RESULTS COMPARISON: 4H MA Crossover on {sym}")
        print(f"{'Rank':<5} | {'SL':<5} | {'TP':<5} | {'Trades':<8} | {'Win Rate':<10} | {'PF':<8} | {'Max DD':<10} | {'Sharpe':<8} | {'Net PnL':<10}")
        print("-" * 85)
        
        for i, r in enumerate(results):
            marker = " "
            if r["SL"] == 1.0 and r["TP"] == 2.0: marker = "S" # Scalping
            if r["SL"] == 2.0 and r["TP"] == 3.5: marker = "I" # Intraday
            if r["SL"] == 1.5 and r["TP"] == 4.5: marker = "A" # Aggressive
            
            if i < 5 or marker != " ":
                print(f"#{i+1:<4} | {r['SL']:<5.1f} | {r['TP']:<5.1f} | {r['Trades']:<8.0f} | {r['WinRate']*100:<9.2f}% | {r['ProfitFactor']:<8.2f} | {r['MaxDD']*100:<9.2f}% | {r['Sharpe']:<8.2f} | ${r['PnL']:<9.2f} [{marker}]")

if __name__ == "__main__":
    main()
