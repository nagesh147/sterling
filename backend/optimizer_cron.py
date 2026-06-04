import sys
import os
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.sterling_engine.config import default_config
from app.engines.sterling_engine.optimizer import _pf_exp
from report_metrics_aggressive import get_candles_paper, replay_strategy

WHITELIST_PATH = os.path.join(os.path.dirname(__file__), "app", "engines", "scalping", "whitelist.json")

def run_weekly_optimization():
    print(f"[{datetime.now()}] Starting Weekly Walk-Forward Optimizer...")
    symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
    
    strategies = ["price_action", "smc", "ma_crossover", "mean_reversion", "breakout"]
    
    timeframes = [
        {"exec": "1m", "macro": "15m", "level": "1h"},
        {"exec": "3m", "macro": "15m", "level": "1h"},
        {"exec": "5m", "macro": "1h", "level": "4h"},
        {"exec": "15m", "macro": "4h", "level": "4h"},
        {"exec": "30m", "macro": "4h", "level": "4h"},
        {"exec": "45m", "macro": "4h", "level": "4h"},
        {"exec": "1h", "macro": "4h", "level": "4h"},
        {"exec": "2h", "macro": "4h", "level": "4h"},
        {"exec": "4h", "macro": "4h", "level": "4h"}
    ]
    
    config = default_config()
    prof = config.profiles.get("aggressive")
    
    test_prof = prof.model_copy()
    test_prof.enable_price_action = True
    test_prof.enable_smc = True
    test_prof.enable_ma_crossover = True
    test_prof.enable_mean_reversion = True
    test_prof.enable_breakout = True
    test_prof.enable_delta_gamma = False
    
    if os.path.exists(WHITELIST_PATH):
        try:
            with open(WHITELIST_PATH, "r") as f:
                whitelist = json.load(f)
        except Exception:
            whitelist = {}
    else:
        whitelist = {}
        
    all_unfiltered_trades = []
    all_whitelisted_trades = []
        
    for strat in strategies:
        if strat not in whitelist:
            whitelist[strat] = {}
        for sym in symbols:
            if sym not in whitelist[strat]:
                whitelist[strat][sym] = {}
                
            print(f"Profiling {strat.upper()} on {sym}...")
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
            
            ta = replay_strategy(sym, cM, cE, cL, test_prof, tsM, 1, 60, strat, use_trailing_sl=False)
            
            is_valid = True
            if len(ta) > 0:
                pf_a, exp_a, n_a = _pf_exp(ta)
                if pf_a < 1.0:
                    is_valid = False
            else:
                # Treat 0 trades as enabled to allow future exploration
                is_valid = True
                
            whitelist[strat][sym][exec_tf] = is_valid
            status = "ENABLED" if is_valid else "DISABLED"
            print(f"  -> {exec_tf}: {status} (Trades: {len(ta)})")
            
            # Accumulate trades for the impact report
            all_unfiltered_trades.extend(ta)
            if is_valid:
                all_whitelisted_trades.extend(ta)

    # Write the new ruleset to disk
    with open(WHITELIST_PATH, "w") as f:
        json.dump(whitelist, f, indent=4)
        
    print(f"[{datetime.now()}] Optimization complete. Whitelist updated.")
    
    # Generate Impact Metrics
    def get_stats(pnl_list):
        if not pnl_list: return 0, 0, 0, 0
        pf, exp, n = _pf_exp(pnl_list)
        wins = len([t for t in pnl_list if t > 0])
        wr = (wins / len(pnl_list)) * 100
        return pf, exp, len(pnl_list), wr
        
    pf_u, exp_u, len_u, wr_u = get_stats(all_unfiltered_trades)
    pf_f, exp_f, len_f, wr_f = get_stats(all_whitelisted_trades)
    
    impact_data = {
        "unfiltered": {
            "trades": len_u,
            "profit_factor": round(pf_u, 2),
            "expectancy": round(exp_u, 2),
            "win_rate": round(wr_u, 1)
        },
        "whitelisted": {
            "trades": len_f,
            "profit_factor": round(pf_f, 2),
            "expectancy": round(exp_f, 2),
            "win_rate": round(wr_f, 1)
        },
        "improvement_pf": round(pf_f - pf_u, 2),
        "blocked_toxic_trades": len_u - len_f,
        "last_updated": datetime.now().isoformat()
    }
    
    IMPACT_PATH = os.path.join(os.path.dirname(__file__), "app", "engines", "scalping", "impact.json")
    with open(IMPACT_PATH, "w") as f:
        json.dump(impact_data, f, indent=4)
        
    print(f"[{datetime.now()}] Impact Report saved to {IMPACT_PATH}")

if __name__ == '__main__':
    run_weekly_optimization()
