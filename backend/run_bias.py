import sqlite3
import pandas as pd
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.scalping.check_bias_distribution import run_bias_diagnostic

def run():
    conn = sqlite3.connect('sterling_paper.db')
    cursor = conn.cursor()
    
    # 1. Fetch 4H OHLCV
    query = "SELECT time, open, high, low, close, volume FROM ohlcv WHERE resolution IN ('4h', '4H', '240') ORDER BY time ASC;"
    df_4h = pd.read_sql_query(query, conn)
    df_4h = df_4h.sort_values('time').reset_index(drop=True)
    
    # 2. Fetch Trades from positions
    cursor.execute("SELECT entry_ts, data, status FROM positions;")
    positions = cursor.fetchall()
    
    trades = []
    long_count = 0
    short_count = 0
    
    for ts, data_str, status in positions:
        try:
            data = json.loads(data_str)
            side = data.get('side', data.get('direction', data.get('type', None)))
            
            # sometimes side is "BUY" or "SELL"
            if side:
                side_lower = str(side).lower()
                if side_lower in ['buy', 'long', 'bullish']:
                    trades.append({'timestamp': ts, 'side': 'long'})
                    long_count += 1
                elif side_lower in ['sell', 'short', 'bearish']:
                    trades.append({'timestamp': ts, 'side': 'short'})
                    short_count += 1
                else:
                    print(f"Unknown side: {side}")
        except Exception as e:
            pass
            
    df_trades = pd.DataFrame(trades)
    
    print(f"Loaded {len(df_4h)} 4H bars.")
    print(f"Found {len(positions)} total positions.")
    print(f"Parsed trades: {long_count} longs, {short_count} shorts.")
    
    if not df_trades.empty:
        run_bias_diagnostic(df_4h, df_trades)
    else:
        print("No trades found.")

if __name__ == '__main__':
    run()
