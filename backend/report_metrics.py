import sys
import os
import sqlite3
import pandas as pd
import numpy as np
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.sterling_engine.config import default_config, ScalpingProfile
from app.engines.sterling_engine.optimizer import _pf_exp, W_EXEC, W_MACRO, _exit_fixed
from app.engines.sterling_engine.scanner import scan_symbol
from app.schemas.market import Candle

def get_candles_paper(symbol, resolution, limit=20000):
    conn = sqlite3.connect('backend/sterling_paper.db')
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT time, open, high, low, close, volume FROM ohlcv "
            "WHERE symbol=? AND resolution=? ORDER BY time DESC LIMIT ?",
            (symbol, resolution, limit),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()
    rows.reverse()
    return [Candle(timestamp_ms=int(r[0])*1000, open=r[1], high=r[2], low=r[3], close=r[4], volume=r[5]) for r in rows]

def get_available_symbols():
    conn = sqlite3.connect('backend/sterling_paper.db')
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT symbol FROM ohlcv WHERE resolution='15m' GROUP BY symbol HAVING count(*) > 1000;")
        rows = cursor.fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]

def _exit_with_trailing_sl(cE, i, is_long, entry, sl, tp, maxh):
    current_sl = sl
    for k in range(i + 1, min(i + 1 + maxh, len(cE))):
        hi, lo = cE[k].high, cE[k].low
        if is_long:
            if lo <= current_sl: return current_sl, k
            if hi >= tp: return tp, k
            trail_dist = entry * 0.015
            if hi - trail_dist > current_sl:
                current_sl = hi - trail_dist
        else:
            if hi >= current_sl: return current_sl, k
            if lo <= tp: return tp, k
            trail_dist = entry * 0.015
            if lo + trail_dist < current_sl:
                current_sl = lo + trail_dist
    j = min(i + maxh, len(cE) - 1)
    return cE[j].close, j

def replay_strategy(sym, cM, cE, cfg: ScalpingProfile, tsM, step, maxh, strategy_name, use_trailing_sl=True):
    import bisect
    out = []
    cooldown, cj = -1, -1
    n = len(cE)
    i = W_EXEC
    while i < n - 1:
        if i <= cooldown:
            i += step; continue
        j = bisect.bisect_right(tsM, cE[i].timestamp_ms)
        if j < W_MACRO:
            i += step; continue
        
        signals = scan_symbol(sym, cM[j - W_MACRO:j], cE[i - W_EXEC:i + 1], cfg, 20, 20)
        sig = None
        for s in signals:
            if s.strategy == strategy_name and s.entry_ok and s.direction in ("long", "short"):
                sig = s
                break
                
        if sig and sig.entry and sig.stop_loss and sig.take_profit:
            is_long = sig.direction == "long"
            if use_trailing_sl:
                ex, ck = _exit_with_trailing_sl(cE, i, is_long, sig.entry, sig.stop_loss, sig.take_profit, maxh)
            else:
                ex, ck = _exit_fixed(cE, i, is_long, sig.entry, sig.stop_loss, sig.take_profit, maxh)
            
            pnl = (1 if is_long else -1) * (ex - sig.entry) / abs(sig.entry - sig.stop_loss)
            out.append(pnl)
            cooldown = ck
        i += step
    return out

def generate_report():
    symbols = get_available_symbols()
    # Let's limit to top 3 symbols for speed in backtest reporting
    top_symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
    symbols = [s for s in top_symbols if s in symbols]
    
    strategies = [
        ("price_action", "Price Action"),
        ("smc", "SMC"),
        ("ma_crossover", "MA Crossover"),
        ("mean_reversion", "Mean Reversion"),
        ("breakout", "Breakout Momentum"),
        ("delta_gamma", "Delta-Gamma")
    ]
    
    config = default_config()
    profiles = ["intraday", "scalping", "aggressive"]
    
    report_lines = []
    report_lines.append("# Scalping Engine Performance Report: Before & After Polishes")
    report_lines.append("Evaluated over real historical data (fast simulated dataset) across 3 primary assets (BTC, ETH, SOL).")
    report_lines.append("The 'Before' metrics reflect fixed SL/TP logic and loose parameters. The 'After' metrics integrate trailing stops and the recent execution constraints (e.g., minimum R:R and mathematical expectancy constraints).\n")
    
    print("Generating report, evaluating profiles...")
    for prof_name in profiles:
        prof = config.profiles.get(prof_name)
        if not prof: continue
        report_lines.append(f"## {prof_name.upper()} Profile (Macro: {prof.macro_timeframe}, Exec: {prof.execution_timeframe})")
        report_lines.append("| Strategy | Before (PF) | Before (Exp) | After (PF) | After (Exp) | After (Sharpe) | After Win% |")
        report_lines.append("|---|---|---|---|---|---|---|")
        
        print(f"Profile: {prof_name.upper()}")
        
        # Determine step size to speed up aggressive profile
        step_val = 2 if prof.execution_timeframe != "1m" else 10
        
        for strat_id, strat_label in strategies:
            test_prof_before = prof.model_copy()
            test_prof_after = prof.model_copy()
            for s, _ in strategies:
                setattr(test_prof_before, f"enable_{s}", False)
                setattr(test_prof_after, f"enable_{s}", False)
            setattr(test_prof_before, f"enable_{strat_id}", True)
            setattr(test_prof_after, f"enable_{strat_id}", True)
            
            # Disable trend filter and set min_rr low for "Before" to emulate relaxed logic
            test_prof_before.macro_trend_filter = False
            test_prof_before.min_rr = 1.0
            
            trades_before = []
            trades_after = []
            
            for sym in symbols:
                cM = get_candles_paper(sym, prof.macro_timeframe, limit=10000)
                cE = get_candles_paper(sym, prof.execution_timeframe, limit=20000)
                if not cM or not cE: continue
                tsM = [c.timestamp_ms for c in cM]
                
                # Before simulation
                tb = replay_strategy(sym, cM, cE, test_prof_before, tsM, step_val, 96, strat_id, use_trailing_sl=False)
                trades_before.extend(tb)
                
                # After simulation
                ta = replay_strategy(sym, cM, cE, test_prof_after, tsM, step_val, 96, strat_id, use_trailing_sl=True)
                trades_after.extend(ta)
                
            if len(trades_before) == 0 and len(trades_after) == 0:
                report_lines.append(f"| {strat_label} | 0.00 | 0.00R | 0.00 | 0.00R | 0.00 | 0.0% |")
                continue
                
            pf_b, exp_b, n_b = _pf_exp(trades_before)
            pf_a, exp_a, n_a = _pf_exp(trades_after)
            
            if len(trades_after) > 0:
                wins_a = sum(1 for t in trades_after if t > 0)
                wr_a = wins_a / len(trades_after)
                std_a = np.std(trades_after)
                sharpe_a = (np.mean(trades_after) / std_a) * np.sqrt(252 * (len(trades_after)/365.0)) if std_a != 0 else 0
            else:
                wr_a = 0
                sharpe_a = 0
                
            report_lines.append(f"| {strat_label} | {pf_b:.2f} | {exp_b:.2f}R | **{pf_a:.2f}** | **{exp_a:.2f}R** | {sharpe_a:.2f} | {wr_a*100:.1f}% |")
            
        report_lines.append("\n")

    with open("performance_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print("Report written to performance_report.md")

if __name__ == '__main__':
    generate_report()
