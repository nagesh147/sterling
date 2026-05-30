import sqlite3
import pandas as pd
import numpy as np
import os
import time
from ta import add_all_ta_features

DB_PATH = 'sterling_paper.db'

def calculate_indicators(df):
    try:
        # Sort by time to ensure calculations are correct
        df = df.sort_values('time')
        df = add_all_ta_features(
            df, open="open", high="high", low="low", close="close", volume="volume", fillna=True
        )
    except Exception as e:
        print(f"[!] Warning: Could not compute some TA features: {e}")
        
    return df

def main():
    print("="*80)
    print(" BUILDING HIGH-SPEED VECTOR DATA STORE (RESUMABLE) ")
    print("="*80)
    
    if not os.path.exists(DB_PATH):
        print(f"[!] Database {DB_PATH} not found.")
        return

    start_time = time.time()
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Get list of symbols
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM ohlcv WHERE resolution='1m'")
        symbols = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"[!] Could not read symbols from database: {e}")
        conn.close()
        return
        
    print(f"[i] Found {len(symbols)} symbols to process: {symbols}")
    
    for symbol in symbols:
        output_file = f'vector_store_1m_{symbol}.parquet'
        
        if os.path.exists(output_file):
            print(f"[i] {output_file} already exists. Skipping {symbol}... (RESUMED)")
            continue
            
        print(f"\n[i] Extracting raw 1m OHLCV data for {symbol}...")
        
        query = f"SELECT time, symbol, open, high, low, close, volume FROM ohlcv WHERE resolution='1m' AND symbol='{symbol}' ORDER BY time ASC"
        df = pd.read_sql_query(query, conn)
        
        if len(df) == 0:
            print(f"[!] No data found for {symbol}.")
            continue
            
        print(f"[i] Successfully extracted {len(df):,} candles for {symbol}.")
        print(f"[i] Applying Vectorized Indicator Math for {symbol} (this may take a minute)...")
        
        df_processed = calculate_indicators(df)
        
        print(f"[i] Saving {len(df_processed)} pre-computed rows to {output_file}...")
        df_processed.to_parquet(output_file, engine='pyarrow', compression='snappy')
        print(f"[i] Finished {symbol}.")
        
    conn.close()
    
    end_time = time.time()
    print("="*80)
    print(f" SUCCESS! Vector Store build process completed in {end_time - start_time:.2f} seconds.")
    print("="*80)

if __name__ == "__main__":
    main()
