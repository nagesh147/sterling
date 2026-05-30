import sqlite3
import pandas as pd
import numpy as np
import os
import time
from ta import add_all_ta_features

DB_PATH = 'sterling_paper.db'
OUTPUT_PARQUET = 'vector_store_1m.parquet'

def calculate_indicators(df):
    print(f"  -> Pre-computing 100+ community indicators for symbol...")
    
    # The 'ta' library requires enough data to calculate everything.
    # It automatically adds 80+ columns including MACD, RSI, ADX, Ichimoku, Stochastic, etc.
    try:
        df = add_all_ta_features(
            df, open="open", high="high", low="low", close="close", volume="volume", fillna=True
        )
    except Exception as e:
        print(f"[!] Warning: Could not compute some TA features: {e}")
        
    return df

def main():
    print("="*80)
    print(" BUILDING HIGH-SPEED VECTOR DATA STORE ")
    print("="*80)
    
    if not os.path.exists(DB_PATH):
        print(f"[!] Database {DB_PATH} not found.")
        return

    start_time = time.time()
    
    print("[i] Extracting raw 1m OHLCV data from SQLite (reading in chunks)...")
    conn = sqlite3.connect(DB_PATH)
    
    chunk_size = 100000
    chunks = []
    
    try:
        # We read in chunks so you can see live progress in the terminal
        query = "SELECT time, symbol, open, high, low, close, volume FROM ohlcv ORDER BY time ASC"
        for i, chunk in enumerate(pd.read_sql_query(query, conn, chunksize=chunk_size)):
            chunks.append(chunk)
            print(f"  -> Extracted chunk {i+1} ({len(chunk)} rows)...")
    except Exception as e:
        print(f"[!] Could not extract data: {e}")
        
    conn.close()
    
    if not chunks:
        print("[!] No data found in database.")
        return
        
    df = pd.concat(chunks, ignore_index=True)
    print(f"\n[i] Successfully extracted {len(df):,} total candles.")
    print("[i] Applying Vectorized Indicator Math (this may take a few seconds)...")
    
    # Group by symbol in case multiple assets exist, apply indicators to each independently
    df_processed = df.groupby('symbol', group_keys=False).apply(calculate_indicators)
    
    print(f"[i] Saving {len(df_processed)} pre-computed rows to {OUTPUT_PARQUET}...")
    
    # Save to Parquet - highly compressed, extremely fast read times
    df_processed.to_parquet(OUTPUT_PARQUET, engine='pyarrow', compression='snappy')
    
    end_time = time.time()
    print("="*80)
    print(f" SUCCESS! Vector Store built in {end_time - start_time:.2f} seconds.")
    print(f" Future 5-Year backtests loading {OUTPUT_PARQUET} will now execute in < 2 seconds.")
    print("="*80)

if __name__ == "__main__":
    main()
