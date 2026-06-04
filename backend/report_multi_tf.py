import sys
import os
import sqlite3
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.sterling_engine.config import default_config, ScalpingProfile
from app.engines.sterling_engine.optimizer import _pf_exp
from report_metrics_aggressive import get_candles_paper, replay_strategy

def report_multi_tf():
    symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
    timeframes = [
        {"exec": "1m", "macro": "15m", "level": "1h"},
        {"exec": "5m", "macro": "1h", "level": "4h"},
        {"exec": "15m", "macro": "4h", "level": "4h"},
        {"exec": "30m", "macro": "4h", "level": "4h"},
        {"exec": "1h", "macro": "4h", "level": "4h"},
        {"exec": "2h", "macro": "4h", "level": "4h"},
        {"exec": "4h", "macro": "4h", "level": "4h"},
    ]
    
    config = default_config()
    prof = config.profiles.get("aggressive")
    
    test_prof = prof.model_copy()
    test_prof.enable_breakout = True
    test_prof.use_optimized = True
    test_prof.min_rr = 0.8
    test_prof.allow_long = True
    test_prof.allow_short = True
    
    results = []
    
    for tf in timeframes:
        for sym in symbols:
            # We must set the config timeframes
            test_prof.execution_timeframe = tf["exec"]
            test_prof.macro_timeframe = tf["macro"]
            
            # Use smaller limits for larger timeframes to avoid missing data if db is small
            # But the db limit specifies max rows.
            cE = get_candles_paper(sym, tf["exec"], limit=5000)
            cM = get_candles_paper(sym, tf["macro"], limit=2000)
            cL = get_candles_paper(sym, tf["level"], limit=1000)
            
            if not cM or not cE or not cL:
                continue
            
            tsM = [c.timestamp_ms for c in cM]
            
            # the replay_strategy takes c1h, we pass cL
            ta = replay_strategy(sym, cM, cE, cL, test_prof, tsM, 1, 60, "breakout", use_trailing_sl=False)
            
            if len(ta) > 0:
                pf_a, exp_a, n_a = _pf_exp(ta)
                wins_a = sum(1 for t in ta if t > 0)
                wr_a = wins_a / len(ta)
                results.append(f"| {sym} | {tf['exec']} | {len(ta)} | {pf_a:.2f} | {exp_a:.2f}R | {wr_a*100:.1f}% |")
            else:
                results.append(f"| {sym} | {tf['exec']} | 0 | 0.00 | 0.00R | 0.0% |")
                
    print("\n## Ultra Breakout Momentum - Multi-Timeframe Analysis")
    print("| Asset | Timeframe | Trades | Profit Factor | Expectancy | Win Rate |")
    print("|-------|-----------|--------|---------------|------------|----------|")
    for r in results:
        print(r)

if __name__ == '__main__':
    report_multi_tf()
