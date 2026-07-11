import sqlite3
import pandas as pd
import json
import sys
import os

# Ensure the app module is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engines.sterling_engine.check_bias_distribution import run_bias_diagnostic

def evaluate_bias_from_db(db_path="sterling_paper.db"):
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return
        
    conn = sqlite3.connect(db_path)
    
    print("Loading 4H OHLCV market data...")
    # Prioritize 4H / 240m resolution to act as the macro benchmark
    query = "SELECT time, open, high, low, close, volume FROM ohlcv WHERE resolution IN ('4h', '4H', '240', '240m') ORDER BY time ASC;"
    df_4h = pd.read_sql_query(query, conn)
    
    if df_4h.empty:
        print("Could not find 4H OHLCV data. Falling back to the closest available resolution to simulate benchmark...")
        df_4h = pd.read_sql_query("SELECT time, open, high, low, close, volume FROM ohlcv ORDER BY time ASC LIMIT 5000;", conn)
    
    df_4h = df_4h.sort_values('time').reset_index(drop=True)
    
    print("Extracting executed trades from paper trading session...")
    cursor = conn.cursor()
    
    # In the Sterling architecture, live/paper executed trades reside in `positions` or `signal_history`
    # We will aggregate both to ensure we capture the full execution distribution
    trades = []
    
    # 1. Check positions
    cursor.execute("SELECT entry_ts, data FROM positions;")
    positions = cursor.fetchall()
    for ts, data_str in positions:
        try:
            data = json.loads(data_str)
            side = data.get('side', data.get('direction', data.get('type', None)))
            if side:
                trades.append({'timestamp': ts, 'side': str(side).lower()})
        except Exception:
            pass

    # 2. Check signal_history (if positions is empty, use raw signals)
    if not trades:
        cursor.execute("SELECT timestamp_ms, data FROM signal_history;")
        signals = cursor.fetchall()
        for ts, data_str in signals:
            try:
                data = json.loads(data_str)
                side = data.get('side', data.get('direction', None))
                if side:
                    trades.append({'timestamp': ts, 'side': str(side).lower()})
            except Exception:
                pass

    df_trades = pd.DataFrame(trades)
    
    # Standardize trade sides to 'long' and 'short'
    if not df_trades.empty:
        df_trades['side'] = df_trades['side'].replace({'buy': 'long', 'bullish': 'long', 'sell': 'short', 'bearish': 'short'})
        
        # Filter out anything that isn't cleanly long or short
        df_trades = df_trades[df_trades['side'].isin(['long', 'short'])]
        
        print(f"Total OHLCV 4H Bars: {len(df_4h)}")
        print(f"Total Executed Trades: {len(df_trades)}")
        print("Running Bias Diagnostic...\n")
        
        run_bias_diagnostic(df_4h, df_trades)
    else:
        print("\n❌ No trades found in the local `sterling_paper.db`.")
        print("Please ensure your Paper Trading session has executed trades before running the diagnostic.")
        print("Once the engine has executed a statistically significant sample (>50 trades), run this script again.")

if __name__ == '__main__':
    evaluate_bias_from_db()
