import pandas as pd
import numpy as np
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.edge.strategies import SIGNAL_FNS, resample
from app.engines.edge.registry import PROFILE_CONFIG
from app.engines.edge.robustness import run_robustness_gate
from comprehensive_backtest import simulate

def load_symbol_fast(path: str) -> pd.DataFrame:
    cols = ["time", "symbol", "open", "high", "low", "close", "volume", "volatility_atr"]
    df = pd.read_parquet(path, columns=cols)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"volatility_atr": "atr"}).set_index("time").sort_index()
    # Limit to 100k rows for faster comparative test
    return df.tail(100000)

def main():
    print("=== STERLING V2 (AFTER) FAST BACKTESTER ===")
    files = sorted(glob.glob("backend/vector_store_1m_*.parquet"))
    if not files:
        files = sorted(glob.glob("vector_store_1m_*.parquet"))
        
    print(f"Found {len(files)} symbols. Running V2 State Machine Engine...\n")
    
    results = []
    
    for f in files:
        symbol = os.path.basename(f).split("_")[-1].replace(".parquet", "")
        df_1m = load_symbol_fast(f)
        
        for rule, label in [("5min", "5m"), ("15min", "15m"), ("1h", "1h")]:
            df_tf = resample(df_1m, rule)
            
            for strat, fn in SIGNAL_FNS.items():
                if strat not in ["vwap_cross", "bb_rsi_reversion"]:
                    continue
                    
                sigs = fn(df_tf)
                if sigs.sum() == 0:
                    continue
                    
                for profile_name, risk_config in PROFILE_CONFIG.items():
                    sim = simulate(df_tf, sigs, risk_config)
                    if sim["total_trades"] < 5:
                        continue
                        
                    robustness = run_robustness_gate(sim["trades"], sim["return_stream"], num_trials=50)
                    
                    results.append({
                        "Symbol": symbol,
                        "TF": label,
                        "Strat": strat,
                        "Profile": profile_name,
                        "Trades": sim["total_trades"],
                        "Return": f"{sim['net_return']*100:.2f}%",
                        "MaxDD": f"{sim['max_dd']*100:.2f}%",
                        "Sharpe": f"{robustness['oos_sharpe']:.2f}",
                        "DSR": f"{robustness['dsr']:.2f}",
                        "WFA": "Pass" if robustness.get("wfa_passed") else "Fail",
                        "EndCap": f"${sim['end_capital']:,.2f}"
                    })

    # Print V2 Markdown Report
    print("### V2 Architecture Report (After)")
    print("| Symbol | TF | Strategy | Profile | Trades | Return | Max DD | OOS Sharpe | DSR | WFA | End Capital |")
    print("|--------|----|----------|---------|--------|--------|--------|------------|-----|-----|-------------|")
    for r in results:
        print(f"| {r['Symbol']} | {r['TF']} | {r['Strat']} | {r['Profile']} | {r['Trades']} | {r['Return']} | {r['MaxDD']} | {r['Sharpe']} | {r['DSR']} | {r['WFA']} | {r['EndCap']} |")

if __name__ == "__main__":
    main()
