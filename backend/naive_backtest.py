import pandas as pd
import numpy as np
import glob
import os
import time
from pathlib import Path

# V1 Setup: No dynamic scaling, fixed percentages, no slippage
STARTING_CAPITAL = 100000

# Minimal mock registry for V1
TIMEFRAMES = [("5min", "5m"), ("15min", "15m"), ("1h", "1h")]
STRATEGIES = ["vwap_cross", "bb_rsi_reversion"]
PROFILES = ["spot", "futures", "options"]

def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg_dict = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    if "atr" in df.columns:
        agg_dict["atr"] = "last"
    return df.resample(rule).agg(agg_dict).dropna()

def apply_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Dummy VWAP
    df["vwap"] = (df["high"] + df["low"] + df["close"]) / 3
    # Dummy BB
    df["bb_lower"] = df["close"].rolling(20).mean() - 2 * df["close"].rolling(20).std()
    # Dummy RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    return df.bfill()

def generate_signals(df: pd.DataFrame, strategy: str) -> np.ndarray:
    if strategy == "vwap_cross":
        return (df["close"] > df["vwap"]).astype(int).to_numpy()
    elif strategy == "bb_rsi_reversion":
        return ((df["close"] < df["bb_lower"]) & (df["rsi"] < 30)).astype(int).to_numpy()
    return np.zeros(len(df))

def naive_simulate(df: pd.DataFrame, signals: np.ndarray, sl_pct: float, tp_pct: float) -> dict:
    """V1 Vectorized 'Jump' logic: 0 slippage, fixed % stops, no scaling"""
    close = df["close"].to_numpy()
    n = len(close)
    
    trades = []
    equity = STARTING_CAPITAL
    equity_curve = [equity]
    
    in_trade = False
    entry_price = 0.0
    
    for i in range(1, n):
        if not in_trade and signals[i-1]:
            in_trade = True
            entry_price = close[i]  # Perfect fill next bar
        elif in_trade:
            # Check fixed SL/TP
            ret = (close[i] - entry_price) / entry_price
            if ret <= -sl_pct or ret >= tp_pct:
                # Close trade
                pnl = equity * ret  # Risking full account balance proportionally
                equity += pnl
                trades.append(ret)
                in_trade = False
        
        equity_curve.append(equity)
        
    equity_curve = np.array(equity_curve)
    total_ret = (equity - STARTING_CAPITAL) / STARTING_CAPITAL
    max_dd = 0.0
    if len(equity_curve) > 0:
        roll_max = np.maximum.accumulate(equity_curve)
        drawdowns = (roll_max - equity_curve) / roll_max
        max_dd = np.max(drawdowns)
        
    # Naive Sharpe
    returns = np.diff(equity_curve) / equity_curve[:-1]
    sharpe = 0.0
    if len(returns) > 0 and np.std(returns) != 0:
        sharpe = np.sqrt(252 * 24 * 60) * np.mean(returns) / np.std(returns)
        
    return {
        "trades": len(trades),
        "total_return": total_ret,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "end_capital": equity
    }

def load_symbol(path: str) -> pd.DataFrame:
    cols = ["time", "symbol", "open", "high", "low", "close", "volume", "volatility_atr"]
    df = pd.read_parquet(path, columns=cols)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"volatility_atr": "atr"}).set_index("time").sort_index()
    # Limit to 100k rows for faster naive test
    return df.tail(100000)

def main():
    print("=== STERLING V1 NAIVE BACKTESTER ===")
    files = sorted(glob.glob("backend/vector_store_1m_*.parquet"))
    if not files:
        files = sorted(glob.glob("vector_store_1m_*.parquet"))
        
    print(f"Found {len(files)} symbols. Running V1 Naive Engine...\n")
    
    results = []
    
    for f in files:
        symbol = os.path.basename(f).split("_")[-1].replace(".parquet", "")
        df_1m = load_symbol(f)
        
        for rule, label in TIMEFRAMES:
            df_tf = resample(df_1m, rule)
            df_ind = apply_indicators(df_tf)
            
            for strat in STRATEGIES:
                sigs = generate_signals(df_ind, strat)
                if sigs.sum() == 0:
                    continue
                    
                for profile in PROFILES:
                    # V1 mapped profiles to simple fixed percentages
                    if profile == "spot":
                        sl, tp = 0.05, 0.10
                    elif profile == "futures":
                        sl, tp = 0.02, 0.04
                    else: # options
                        sl, tp = 0.10, 0.20
                        
                    sim = naive_simulate(df_ind, sigs, sl, tp)
                    
                    results.append({
                        "Symbol": symbol,
                        "TF": label,
                        "Strat": strat,
                        "Profile": profile,
                        "Trades": sim["trades"],
                        "Return": f"{sim['total_return']*100:.2f}%",
                        "MaxDD": f"{sim['max_dd']*100:.2f}%",
                        "Sharpe": f"{sim['sharpe']:.2f}",
                        "EndCap": f"${sim['end_capital']:,.2f}"
                    })

    # Print V1 Markdown Report
    print("### V1 Architecture Report (Before)")
    print("| Symbol | TF | Strategy | Profile | Trades | Return | Max DD | Sharpe | End Capital |")
    print("|--------|----|----------|---------|--------|--------|--------|--------|-------------|")
    for r in results:
        print(f"| {r['Symbol']} | {r['TF']} | {r['Strat']} | {r['Profile']} | {r['Trades']} | {r['Return']} | {r['MaxDD']} | {r['Sharpe']} | {r['EndCap']} |")

if __name__ == "__main__":
    main()
