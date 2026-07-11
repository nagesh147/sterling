import sqlite3
import pandas as pd
import json
import time
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.schemas.market import Candle

def simulate_2_years(symbol="AAVEUSD"):
    db_path = os.environ.get("STERLING_DB_PATH", "sterling_paper.db")
    # Offline study script only — refuse unscoped wipes against non-paper DBs.
    if (
        os.path.basename(db_path) != "sterling_paper.db"
        and os.environ.get("STERLING_ALLOW_SIM_DELETE") != "1"
    ):
        raise SystemExit(
            f"Refusing DELETE on {db_path!r}. "
            "Use sterling_paper.db or set STERLING_ALLOW_SIM_DELETE=1."
        )
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Clear previous simulated trades + re-insert as one transaction
        cursor.execute("BEGIN")
        cursor.execute("DELETE FROM positions WHERE id IS NOT NULL;")

        # Fetch historical 4H data (acts as the macro benchmark and trade anchor)
        df_4h = pd.read_sql_query(
            "SELECT time, open, high, low, close, volume FROM ohlcv "
            "WHERE symbol=? AND resolution=? ORDER BY time ASC;",
            conn,
            params=(symbol, "4h"),
        )

        if df_4h.empty:
            print("Missing OHLCV data. Cannot simulate trades.")
            conn.rollback()
            return

        candles_4h_all = [
            Candle(timestamp_ms=int(r['time'])*1000, open=r['open'], high=r['high'], low=r['low'], close=r['close'], volume=r['volume'])
            for _, r in df_4h.iterrows()
        ]

        print(f"Loaded {len(candles_4h_all)} 4H bars for {symbol} (approx 2 years of data).")

        trades_to_insert = []

        # Simulate trade generation across the entire 2-year history
        # We will explicitly bake in the mathematical inequality (the "flaw")
        # Crypto drops fast (large upper wicks for shorts) and grinds up slow (smaller lower wicks)

        for c in candles_4h_all:
            wick_up = c.high - max(c.open, c.close)
            wick_down = min(c.open, c.close) - c.low

            # Flawed SMC check: Hardcoded nominal dollar value instead of % or ATR
            # We will use $1.50 as a hardcoded sweep size since AAVE trades roughly $50-$150
            hardcoded_sweep_size = 1.50

            # Shorts get triggered by large upward flushes (liquidation wicks)
            if wick_up > hardcoded_sweep_size:
                trades_to_insert.append({
                    "entry_ts": int(c.timestamp_ms / 1000),
                    "data": json.dumps({"side": "short", "strategy": "smc", "reason": "flawed nominal dollar wick sweep"})
                })

            # Longs get triggered by downward flushes
            # But wait! If we just make both `> 1.50`, the natural asymmetry of crypto
            # (crashes are faster and leave bigger wicks than grinds) will naturally
            # result in fewer longs being found than shorts over a 2 year period!
            elif wick_down > hardcoded_sweep_size:
                trades_to_insert.append({
                    "entry_ts": int(c.timestamp_ms / 1000),
                    "data": json.dumps({"side": "long", "strategy": "smc", "reason": "flawed nominal dollar wick sweep"})
                })

        print(f"Generated {len(trades_to_insert)} executed trades over 2 years. Inserting into positions table...")

        for t in trades_to_insert:
            unique_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO positions (id, underlying, status, entry_ts, updated_ts, data) VALUES (?, ?, ?, ?, ?, ?)",
                (unique_id, symbol, "OPEN", t['entry_ts'], t['entry_ts'], t['data'])
            )
        conn.commit()
    finally:
        conn.close()

    print("Database successfully populated with 2 years of history. Running evaluate_bias.py...")

if __name__ == '__main__':
    simulate_2_years("AAVEUSD")
