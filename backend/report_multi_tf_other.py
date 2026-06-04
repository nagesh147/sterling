import sys
import os
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.sterling_engine.config import default_config
from app.engines.sterling_engine.optimizer import _pf_exp
from report_metrics_aggressive import get_candles_paper, replay_strategy

def generate_matrix(strategy_name: str):
    print(f"\n--- {strategy_name.upper()} MULTI-TIMEFRAME MATRIX ---")
    symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
    
    timeframes = [
        {"exec": "1m", "macro": "15m", "level": "1h"},
        {"exec": "15m", "macro": "4h", "level": "4h"}
    ]
    
    config = default_config()
    prof = config.profiles.get("aggressive")
    
    test_prof = prof.model_copy()
    test_prof.enable_price_action = True
    test_prof.enable_mean_reversion = True
    test_prof.use_optimized = True
    test_prof.min_rr = 0.8
    test_prof.allow_long = True
    test_prof.allow_short = True
    
    results = []
    
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
            
            ta = replay_strategy(sym, cM, cE, cL, test_prof, tsM, 1, 60, strategy_name, use_trailing_sl=False)
            
            if len(ta) > 0:
                pf_a, exp_a, n_a = _pf_exp(ta)
                win_rate = (len([t for t in ta if t > 0]) / len(ta)) * 100
                results.append({
                    "Asset": sym,
                    "Timeframe": exec_tf,
                    "Trades": len(ta),
                    "Profit Factor": f"{pf_a:.2f}",
                    "Expectancy": f"{exp_a:+.2f}R",
                    "Win Rate": f"{win_rate:.1f}%"
                })
            else:
                results.append({
                    "Asset": sym,
                    "Timeframe": exec_tf,
                    "Trades": 0,
                    "Profit Factor": "-",
                    "Expectancy": "-",
                    "Win Rate": "-"
                })

    df = pd.DataFrame(results)
    print(df.to_string(index=False))

if __name__ == '__main__':
    generate_matrix("price_action")
    generate_matrix("mean_reversion")
