import sys
import os
import json
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.sterling_engine.config import default_config
from app.engines.sterling_engine.optimizer import _pf_exp
from report_metrics_aggressive import get_candles_paper, replay_strategy

WHITELIST_PATH = os.path.join(os.path.dirname(__file__), "app", "engines", "scalping", "whitelist.json")

def generate_impact_report():
    print("Loading Whitelist State...")
    if os.path.exists(WHITELIST_PATH):
        with open(WHITELIST_PATH, "r") as f:
            whitelist = json.load(f)
    else:
        print("Run optimizer_cron.py first.")
        return
        
    strategies = ["price_action", "smc", "ma_crossover", "mean_reversion", "breakout"]
    symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
    
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
    
    all_trades = []
    
    for sym in symbols:
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
            
            for strat in strategies:
                ta = replay_strategy(sym, cM, cE, cL, test_prof, tsM, 1, 60, strat, use_trailing_sl=False)
                
                wl_status = True
                try:
                    wl_status = whitelist[strat][sym][exec_tf]
                except KeyError:
                    pass
                
                for t in ta:
                    all_trades.append({
                        "pnl": t,
                        "whitelisted": wl_status
                    })

    if not all_trades:
        print("No trades found.")
        return

    unfiltered_pnl = [t["pnl"] for t in all_trades]
    filtered_pnl = [t["pnl"] for t in all_trades if t["whitelisted"]]
    
    def get_stats(pnl_list):
        if not pnl_list:
            return 0, 0, 0, 0
        pf, exp, n = _pf_exp(pnl_list)
        wins = len([t for t in pnl_list if t > 0])
        wr = (wins / len(pnl_list)) * 100
        return pf, exp, len(pnl_list), wr
        
    pf_u, exp_u, len_u, wr_u = get_stats(unfiltered_pnl)
    pf_f, exp_f, len_f, wr_f = get_stats(filtered_pnl)
    
    print("\n=============================================")
    print("🔥 SYSTEM-WIDE ORCHESTRATION IMPACT REPORT 🔥")
    print("=============================================")
    print("\n1. UNFILTERED (Brute-Force Retail Approach)")
    print(f"Total Trades Taken : {len_u}")
    print(f"Global Profit Factor: {pf_u:.2f}")
    print(f"Global Expectancy  : {exp_u:+.2f}R")
    print(f"Global Win Rate    : {wr_u:.1f}%")
    
    print("\n2. WHITELISTED (Institutional AI Gated)")
    print(f"Total Trades Taken : {len_f}")
    print(f"Global Profit Factor: {pf_f:.2f}")
    print(f"Global Expectancy  : {exp_f:+.2f}R")
    print(f"Global Win Rate    : {wr_f:.1f}%")
    
    print("\n💡 VERDICT:")
    if pf_f > pf_u:
        print(f"The Whitelist gate improved the entire system Profit Factor by +{(pf_f - pf_u):.2f}.")
        print(f"It successfully blocked {len_u - len_f} toxic, negative-expectancy trades from executing.")
    else:
        print("No significant improvement.")
        
if __name__ == '__main__':
    generate_impact_report()
