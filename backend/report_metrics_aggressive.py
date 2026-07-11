import sys
import os
import sqlite3
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.sterling_engine.config import default_config, ScalpingProfile
from app.engines.sterling_engine.optimizer import _pf_exp, W_EXEC, W_MACRO, _exit_fixed
from app.engines.sterling_engine.scanner import scan_symbol
from app.schemas.market import Candle

def get_candles_paper(symbol, resolution, limit=10000):
    conn = sqlite3.connect('backend/sterling_paper.db')
    try:
        cursor = conn.cursor()
        if resolution == '1m':
            cursor.execute(
                "SELECT timestamp, open, high, low, close, volume FROM ohlcv_1m "
                "WHERE symbol=? ORDER BY timestamp DESC LIMIT ?",
                (symbol, limit),
            )
        else:
            cursor.execute(
                "SELECT time, open, high, low, close, volume FROM ohlcv "
                "WHERE symbol=? AND resolution=? ORDER BY time DESC LIMIT ?",
                (symbol, resolution, limit),
            )
        rows = cursor.fetchall()
    finally:
        conn.close()
    rows.reverse()
    if resolution == '1m':
        # the user script already stores ms? wait, Delta's 1m timestamp is mostly ms or s? 
        # Actually user script did: int(c["time"]) - I assume it's seconds because delta is mostly seconds, wait, delta uses seconds? 
        # But wait, original did `int(r[0])*1000`, so let's just do that for 1m too? 
        # Wait, if Delta API returns seconds or milliseconds... let's check one row.
        pass
    
    # Let's standardize it: assume r[0] is seconds if it's 10 digits, or ms if 13 digits.
    res = []
    for r in rows:
        ts = int(r[0])
        if ts < 10000000000:
            ts *= 1000
        res.append(Candle(timestamp_ms=ts, open=r[1], high=r[2], low=r[3], close=r[4], volume=r[5]))
    return res

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

def replay_strategy(sym, cM, cE, c1h, cfg: ScalpingProfile, tsM, step, maxh, strategy_name, use_trailing_sl=True):
    import bisect
    cfg.use_optimized = True # Enforce ultra mode
    out = []
    cooldown, _cj = -1, -1
    n = len(cE)
    i = W_EXEC
    while i < n - 1:
        if i <= cooldown:
            i += step; continue
        j = bisect.bisect_right(tsM, cE[i].timestamp_ms)
        if j < W_MACRO:
            i += step; continue
            
        ts_1h = [c.timestamp_ms for c in c1h]
        k_1h = bisect.bisect_right(ts_1h, cE[i].timestamp_ms)
        c1h_window = c1h[max(0, k_1h - 50):k_1h]
        
        signals = scan_symbol(sym, cM[j - W_MACRO:j], cE[i - W_EXEC:i + 1], c1h_window, cfg, 20, 20)
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
    symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
    
    strategies = [
        ("price_action", "Price Action"),
        ("smc", "SMC"),
        ("ma_crossover", "MA Crossover"),
        ("mean_reversion", "Mean Reversion"),
        ("breakout", "Breakout Momentum"),
        ("delta_gamma", "Delta-Gamma")
    ]
    
    config = default_config()
    prof = config.profiles.get("aggressive")
    
    report_lines = []
    
    step_val = 2 
    
    for strat_id, strat_label in strategies:
        test_prof_before = prof.model_copy()
        test_prof_after = prof.model_copy()
        for s, _ in strategies:
            setattr(test_prof_before, f"enable_{s}", False)
            setattr(test_prof_after, f"enable_{s}", False)
        setattr(test_prof_before, f"enable_{strat_id}", True)
        setattr(test_prof_after, f"enable_{strat_id}", True)
        
        test_prof_before.macro_trend_filter = False
        test_prof_before.min_rr = 0.5
        
        # for AFTER we also lower min_rr for aggressive 1m scaling to get trades
        test_prof_after.min_rr = 0.8
        
        trades_before = []
        trades_after = []
        
        for sym in symbols:
            cM = get_candles_paper(sym, prof.macro_timeframe, limit=2000)
            cE = get_candles_paper(sym, prof.execution_timeframe, limit=5000)
            c1h = get_candles_paper(sym, "1h", limit=1000)
            if not cM or not cE: continue
            
            # For the backtest, we need a way to pass c1h to the strategies.
            # We must modify replay_strategy to receive c1h as well.
            tsM = [c.timestamp_ms for c in cM]
            
            tb = replay_strategy(sym, cM, cE, c1h, test_prof_before, tsM, step_val, 60, strat_id, use_trailing_sl=False)
            trades_before.extend(tb)
            
            ta = replay_strategy(sym, cM, cE, c1h, test_prof_after, tsM, step_val, 60, strat_id, use_trailing_sl=True)
            trades_after.extend(ta)
            
        if len(trades_before) == 0 and len(trades_after) == 0:
            report_lines.append(f"| {strat_label} | 0.00 | 0.00R | 0.00 | 0.00R | 0.00 | 0.0% |")
            continue
            
        pf_b, exp_b, _n_b = _pf_exp(trades_before)
        pf_a, exp_a, _n_a = _pf_exp(trades_after)
        
        if len(trades_after) > 0:
            wins_a = sum(1 for t in trades_after if t > 0)
            wr_a = wins_a / len(trades_after)
            std_a = np.std(trades_after)
            sharpe_a = (np.mean(trades_after) / std_a) * np.sqrt(252 * (len(trades_after)/(365.0*17))) if std_a != 0 else 0
        else:
            wr_a = 0
            sharpe_a = 0
            
        report_lines.append(f"| {strat_label} | {pf_b:.2f} | {exp_b:.2f}R | **{pf_a:.2f}** | **{exp_a:.2f}R** | {sharpe_a:.2f} | {wr_a*100:.1f}% |")

    print("\n".join(report_lines))

if __name__ == '__main__':
    generate_report()
