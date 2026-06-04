import sys
import os
import sqlite3
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.sterling_engine.config import default_config, ScalpingProfile
from app.engines.sterling_engine.optimizer import _pf_exp
from report_metrics_aggressive import get_candles_paper, replay_strategy

def report_breakout():
    symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
    config = default_config()
    prof = config.profiles.get("aggressive")
    
    test_prof = prof.model_copy()
    test_prof.enable_breakout = True
    test_prof.use_optimized = True
    test_prof.min_rr = 0.8
    
    for sym in symbols:
        cM = get_candles_paper(sym, prof.macro_timeframe, limit=2000)
        cE = get_candles_paper(sym, prof.execution_timeframe, limit=5000)
        c1h = get_candles_paper(sym, "1h", limit=1000)
        if not cM or not cE: continue
        tsM = [c.timestamp_ms for c in cM]
        
        ta = replay_strategy(sym, cM, cE, c1h, test_prof, tsM, 2, 60, "breakout", use_trailing_sl=False)
        
        if len(ta) > 0:
            pf_a, exp_a, n_a = _pf_exp(ta)
            wins_a = sum(1 for t in ta if t > 0)
            wr_a = wins_a / len(ta)
            print(f"Asset: {sym} | Trades: {len(ta)} | PF: {pf_a:.2f} | Exp: {exp_a:.2f}R | Win%: {wr_a*100:.1f}%")
            print(f"Trades: {ta}")
        else:
            print(f"Asset: {sym} | Trades: 0")

if __name__ == '__main__':
    report_breakout()
