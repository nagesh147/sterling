import glob
import os
import sys
import numpy as np
import pandas as pd

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

def simulate_adaptive(df, signals, sl_mult, tp_mult):
    close = df["close"].to_numpy(dtype=np.float64)
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)
    atr = df["atr"].to_numpy(dtype=np.float64)
    
    # Calculate volatility regime scalar
    # 100-period SMA of ATR acts as our baseline "normal" volatility
    atr_sma = pd.Series(atr).rolling(100).mean().to_numpy()
    
    n = len(close)
    trades = []
    sig_idx = np.flatnonzero(signals)
    sp = 0
    while sp < len(sig_idx):
        i = sig_idx[sp]
        sp += 1
        if i >= n - 2 or not np.isfinite(atr[i]) or atr[i] <= 0 or not np.isfinite(atr_sma[i]) or atr_sma[i] <= 0:
            continue
            
        # The core adaptive logic:
        raw_scalar = atr[i] / atr_sma[i]
        # Bound the scalar so we don't go completely insane during flash crashes (e.g. max 2x expansion, max 0.5x compression)
        vol_scalar = max(0.5, min(2.0, raw_scalar))
        
        entry = close[i]
        
        # Adaptive multipliers
        # When vol is high, we expand targets drastically to catch the massive runner, 
        # and we expand the stop slightly to avoid getting wicked out.
        sl = entry - (sl_mult * vol_scalar) * atr[i]
        tp = entry + (tp_mult * vol_scalar) * atr[i]
        
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
    print("Loading BTCUSD vector store...")
    df_1m = pd.read_parquet("/home/nageshmadaram/Sterling/backend/vector_store_1m_BTCUSD.parquet")
    df_1m["time"] = pd.to_datetime(df_1m["time"], unit="s")
    df_1m = df_1m.rename(columns={"volatility_atr": "atr"}).set_index("time").sort_index()
    print(f"Loaded {len(df_1m)} rows.")
    
    # We will test the proven winner: 4h MA Crossover - Intraday (2.0 SL / 3.5 TP)
    tf = "4h"
    strat_name = "ma_crossover"
    sl_mult = 2.0
    tp_mult = 3.5
    
    print(f"\nResampling to {tf}...")
    df_tf = resample(df_1m, tf)
    
    print(f"Running {strat_name} signals...")
    sig_fn = SIGNAL_FNS[strat_name]
    signals = sig_fn(df_tf)
    
    print("\n--- Running STATIC Simulation ---")
    static_returns = simulate_static(df_tf, signals, sl_mult, tp_mult)
    static_metrics = metrics(static_returns, tf)
    
    print("--- Running ADAPTIVE Simulation ---")
    adaptive_returns = simulate_adaptive(df_tf, signals, sl_mult, tp_mult)
    adaptive_metrics = metrics(adaptive_returns, tf)
    
    print("\n" + "="*50)
    print("RESULTS COMPARISON: 4H MA Crossover on BTCUSD")
    print("="*50)
    print(f"{'Metric':<20} | {'Static (Fixed 2.0/3.5)':<25} | {'Adaptive (Vol-Scaled)':<25}")
    print("-" * 75)
    
    def fmt(m, is_pct=False, is_usd=False):
        if is_pct: return f"{m*100:.2f}%"
        if is_usd: return f"${m:.2f}"
        return f"{m:.2f}"

    metrics_list = [
        ("Total Trades", "trades", False, False),
        ("Win Rate", "win_rate", True, False),
        ("Profit Factor", "pf", False, False),
        ("Max Drawdown", "max_dd", True, False),
        ("OOS Sharpe", "sharpe", False, False),
        ("Net Return PnL", "pnl_usd", False, True)
    ]
    
    # Calculate PnL (Starting Capital is $500)
    static_metrics["pnl_usd"] = static_metrics["end_capital"] - STARTING_CAPITAL
    adaptive_metrics["pnl_usd"] = adaptive_metrics["end_capital"] - STARTING_CAPITAL
    
    for label, key, is_pct, is_usd in metrics_list:
        v_static = fmt(static_metrics[key], is_pct, is_usd)
        v_adapt = fmt(adaptive_metrics[key], is_pct, is_usd)
        print(f"{label:<20} | {v_static:<25} | {v_adapt:<25}")

if __name__ == "__main__":
    main()
