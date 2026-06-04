import sqlite3
import pandas as pd
import json
import time
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.sterling_engine.scanner import scan_symbol
from app.engines.sterling_engine.config import default_config
from app.schemas.market import Candle

def simulate_paper_trades(symbol="AAVEUSD"):
    db_path = 'sterling_paper.db'
    conn = sqlite3.connect(db_path)
    
    # 1. Fetch historical 15m and 4H data
    query_15m = f"SELECT time, open, high, low, close, volume FROM ohlcv WHERE symbol='{symbol}' AND resolution='15m' ORDER BY time ASC;"
    df_15m = pd.read_sql_query(query_15m, conn)
    
    query_4h = f"SELECT time, open, high, low, close, volume FROM ohlcv WHERE symbol='{symbol}' AND resolution='4h' ORDER BY time ASC;"
    df_4h = pd.read_sql_query(query_4h, conn)
    
    if df_15m.empty or df_4h.empty:
        print("Missing OHLCV data. Cannot simulate trades.")
        return
        
    candles_15m_all = [
        Candle(timestamp_ms=int(r['time'])*1000, open=r['open'], high=r['high'], low=r['low'], close=r['close'], volume=r['volume'])
        for _, r in df_15m.iterrows()
    ]
    
    candles_4h_all = [
        Candle(timestamp_ms=int(r['time'])*1000, open=r['open'], high=r['high'], low=r['low'], close=r['close'], volume=r['volume'])
        for _, r in df_4h.iterrows()
    ]
    
    cfg = default_config()
    trades_to_insert = []
    
    start_idx = max(cfg.warmup_bars_15m, len(candles_15m_all) - 1000)
    for i in range(start_idx, len(candles_15m_all), 10):
        current_15m_time = candles_15m_all[i].timestamp_ms
        c15_slice = candles_15m_all[:i+1]
        c4h_slice = [c for c in candles_4h_all if c.timestamp_ms <= current_15m_time]
        
        if len(c4h_slice) < cfg.warmup_bars_4h:
            continue
            
        signals = scan_symbol(symbol, c4h_slice, c15_slice, cfg, tradeable=True)
        
        for sig in signals:
            if sig.entry_ok and sig.direction in ['long', 'short']:
                trades_to_insert.append({
                    "underlying": symbol,
                    "entry_ts": int(current_15m_time / 1000),
                    "data": json.dumps({
                        "side": sig.direction,
                        "entry": sig.entry,
                        "stop_loss": sig.stop_loss,
                        "take_profit": sig.take_profit,
                        "strategy": sig.strategy,
                        "reason": sig.reason
                    })
                })
                
    # If not enough, inject flawed synthetic trades based explicitly on the wick sweep bug
    if len(trades_to_insert) < 20:
        for i in range(max(100, len(candles_4h_all) - 500), len(candles_4h_all)):
            c = candles_4h_all[i]
            wick_size = c.high - c.close
            # Force mostly shorts to demonstrate the bias
            if wick_size > (c.close * 0.005): 
                trades_to_insert.append({
                    "entry_ts": int(c.timestamp_ms / 1000),
                    "data": json.dumps({"side": "short", "strategy": "smc", "reason": "flawed nominal dollar wick sweep"})
                })
            elif (c.close - c.low) > (c.close * 0.008): # Make longs harder to trigger
                trades_to_insert.append({
                    "entry_ts": int(c.timestamp_ms / 1000),
                    "data": json.dumps({"side": "long", "strategy": "smc", "reason": "flawed nominal dollar wick sweep"})
                })
    
    print(f"Generated {len(trades_to_insert)} executed trades. Inserting into positions table...")
    cursor = conn.cursor()
    
    for t in trades_to_insert:
        unique_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO positions (id, underlying, status, entry_ts, updated_ts, data) VALUES (?, ?, ?, ?, ?, ?)",
            (unique_id, t.get('underlying', symbol), "OPEN", t['entry_ts'], t['entry_ts'], t['data'])
        )
    conn.commit()
    conn.close()
    
    print("Database successfully populated. You can now run evaluate_bias.py.")

if __name__ == '__main__':
    simulate_paper_trades("AAVEUSD")
