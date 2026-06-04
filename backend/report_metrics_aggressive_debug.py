import sys
import os
import sqlite3
import pandas as pd
from collections import defaultdict
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.sterling_engine.config import default_config, ScalpingProfile
from app.engines.sterling_engine.optimizer import _pf_exp, W_EXEC, W_MACRO, _exit_fixed
from app.engines.sterling_engine.scanner import scan_symbol
from app.schemas.market import Candle

def get_candles_paper(symbol, resolution, limit=10000):
    conn = sqlite3.connect('backend/sterling_paper.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT time, open, high, low, close, volume FROM ohlcv WHERE symbol='{symbol}' AND resolution='{resolution}' ORDER BY time DESC LIMIT {limit};")
    rows = cursor.fetchall()
    conn.close()
    rows.reverse()
    return [Candle(timestamp_ms=int(r[0])*1000, open=r[1], high=r[2], low=r[3], close=r[4], volume=r[5]) for r in rows]

def debug_report():
    symbols = ["BTCUSD"]
    config = default_config()
    prof = config.profiles.get("aggressive")
    prof.enable_price_action = True
    prof.macro_trend_filter = False
    prof.min_rr = 0.5
    
    sym = "BTCUSD"
    cM = get_candles_paper(sym, prof.macro_timeframe, limit=2000)
    cE = get_candles_paper(sym, prof.execution_timeframe, limit=10000)
    
    tsM = [c.timestamp_ms for c in cM]
    print(f"cM length: {len(cM)}, cE length: {len(cE)}")
    
    import bisect
    step = 1
    i = W_EXEC
    signal_count = 0
    valid_count = 0
    while i < len(cE) - 1:
        j = bisect.bisect_right(tsM, cE[i].timestamp_ms)
        if j < W_MACRO:
            i += step; continue
        
        signals = scan_symbol(sym, cM[j - W_MACRO:j], cE[i - W_EXEC:i + 1], prof, 20, 20)
        for s in signals:
            if s.strategy == "price_action":
                signal_count += 1
                if s.entry_ok:
                    valid_count += 1
        i += step
    print(f"Total Price Action signals on 1m: {signal_count}")
    print(f"Total valid signals: {valid_count}")

if __name__ == '__main__':
    debug_report()
