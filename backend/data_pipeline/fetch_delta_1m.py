import sqlite3
import time
import requests
import pandas as pd
from typing import Dict, Any

def sync_delta_1m_history(
    db_path: str, 
    symbol: str, 
    days_to_fetch: int = 14
) -> None:
    """
    Paginates through Delta Exchange v2 historical endpoint to harvest 1m data.
    Safely handles the 2000-candle payload limit per API request.
    """
    base_url = "https://api.india.delta.exchange/v2/history/candles"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # We rely on the global ohlcv table defined in the core system.
    # No need to create ohlcv_1m.

    # Calculate global temporal boundaries
    seconds_per_day = 86400
    end_global = int(time.time())
    start_global = end_global - (days_to_fetch * seconds_per_day)
    
    # Delta API limit = 2000 candles. 1980 mins = ~33 hours per chunk loop
    chunk_step_seconds = 1980 * 60 
    current_start = start_global

    print(f"🚀 Initializing $1m$ Data Harvest for {symbol} | Target: {days_to_fetch} Days")

    while current_start < end_global:
        current_end = min(current_start + chunk_step_seconds, end_global)
        
        params = {
            "symbol": symbol,
            "resolution": "1m",
            "start": current_start,
            "end": current_end
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=15)
            data = response.json()
            
            if not data.get("success") or not data.get("result"):
                print(f"⚠️ Warning or empty block between timestamps {current_start} -> {current_end}")
                current_start = current_end
                continue
                
            candles = data["result"]
            records = []
            
            for c in candles:
                # Map Delta schema parameters cleanly to our local DB format
                records.append((
                    int(c["time"]),
                    symbol,
                    float(c["open"]),
                    float(c["high"]),
                    float(c["low"]),
                    float(c["close"]),
                    float(c["volume"])
                ))
            
            # Use INSERT OR IGNORE to automatically resolve duplicate records across chunk seams
            cursor.executemany("""
                INSERT OR IGNORE INTO ohlcv (time, symbol, resolution, open, high, low, close, volume)
                VALUES (?, ?, '1m', ?, ?, ?, ?, ?)
            """, records)
            conn.commit()
            
            print(f"✅ Ingested {len(records)} bars from timestamp: {current_start}")
            
        except Exception as e:
            print(f"❌ Network/Database failure processing chunk: {str(e)}")
            time.sleep(2) # Backoff logic to mitigate API rate-limits
            
        # Move the slide window forward to start of next batch
        current_start = current_end
        time.sleep(0.2) # Polite scraping delay

    conn.close()
    print(f"🏁 Historical Sync Complete for {symbol}. Aggressive profile ready to backtest.")

if __name__ == '__main__':
    # Fetch 5 YEARS (1825 days) of data for the top 3 assets to backtest 
    for sym in ["BTCUSD", "ETHUSD", "SOLUSD"]:
        sync_delta_1m_history('sterling_paper.db', sym, days_to_fetch=1825)
