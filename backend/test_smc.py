import asyncio
import sqlite3
from pathlib import Path
from typing import List
from app.schemas.market import Candle
from app.engines.indicators.smc import compute_smc

def load_candles(symbol: str, resolution: str, db_path: Path) -> List[Candle]:
    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, timeout=30.0)
    rows = conn.execute(
        "SELECT time, open, high, low, close, volume FROM ohlcv "
        "WHERE symbol=? AND resolution=? ORDER BY time ASC",
        (symbol, resolution),
    ).fetchall()
    conn.close()
    return [
        Candle(timestamp_ms=int(t) * 1000, open=float(o), high=float(h),
               low=float(l), close=float(c), volume=float(v or 0.0))
        for t, o, h, l, c, v in rows
    ]

db_path = Path("sterling_paper.db")
candles = load_candles("BTCUSD", "1h", db_path)
df = compute_smc(candles[-100:])
print(df.columns.tolist())
# print(df.tail(2))
