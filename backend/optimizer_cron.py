import sys
import os
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.scalping.config import default_config
from app.engines.scalping.optimizer import _pf_exp
from report_metrics_aggressive import get_candles_paper, replay_strategy

WHITELIST_PATH = os.path.join(os.path.dirname(__file__), "app", "engines", "scalping", "whitelist.json")

def run_weekly_optimization():
    print(f"[{datetime.now()}] Starting Weekly Walk-Forward Optimizer...")
    symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
    
    # We will test the primary execution profiles
    timeframes = [
        {"exec": "1m", "macro": "15m", "level": "1h"},
        {"exec": "3m", "macro": "15m", "level": "1h"},
        {"exec": "5m", "macro": "1h", "level": "4h"},
        {"exec": "15m", "macro": "4h", "level": "4h"},
        {"exec": "1h", "macro": "4h", "level": "4h"}
    ]
    
    config = default_config()
    prof = config.profiles.get("aggressive")
    
    test_prof = prof.model_copy()
    test_prof.enable_breakout = True
    test_prof.use_optimized = True
    test_prof.min_rr = 0.8
    test_prof.allow_long = True
    test_prof.allow_short = True
    
    # Load existing whitelist to merge
    if os.path.exists(WHITELIST_PATH):
        with open(WHITELIST_PATH, "r") as f:
            whitelist = json.load(f)
    else:
        whitelist = {}
        
    if "breakout" not in whitelist:
        whitelist["breakout"] = {}
        
    for sym in symbols:
        if sym not in whitelist["breakout"]:
            whitelist["breakout"][sym] = {}
            
        print(f"Profiling {sym}...")
        for tf in timeframes:
            exec_tf = tf["exec"]
            test_prof.execution_timeframe = exec_tf
            test_prof.macro_timeframe = tf["macro"]
            
            cE = get_candles_paper(sym, exec_tf, limit=5000)
            cM = get_candles_paper(sym, tf["macro"], limit=2000)
            cL = get_candles_paper(sym, tf["level"], limit=1000)
            
            if not cM or not cE or not cL:
                continue
                
            tsM = [c.timestamp_ms for c in cM]
            
            # Replay the strategy to evaluate edge
            ta = replay_strategy(sym, cM, cE, cL, test_prof, tsM, 1, 60, "breakout", use_trailing_sl=False)
            
            is_valid = True
            if len(ta) > 0:
                pf_a, exp_a, n_a = _pf_exp(ta)
                # Mathematical Edge Filter:
                # We need a Profit Factor >= 1.0 to keep it enabled.
                if pf_a < 1.0:
                    is_valid = False
            else:
                # If no trades fired, leave it enabled so we don't accidentally block a rare but good regime
                is_valid = True
                
            whitelist["breakout"][sym][exec_tf] = is_valid
            status = "ENABLED" if is_valid else "DISABLED"
            print(f"  -> {exec_tf}: {status} (Trades: {len(ta)})")

    # Write the new ruleset to disk
    with open(WHITELIST_PATH, "w") as f:
        json.dump(whitelist, f, indent=4)
        
    print(f"[{datetime.now()}] Optimization complete. Whitelist updated.")

if __name__ == '__main__':
    run_weekly_optimization()
