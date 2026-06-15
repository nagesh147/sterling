import asyncio
from datetime import datetime
import time

def drop_forming(candles_ts, now_ms=None):
    if not candles_ts: return candles_ts
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    if candles_ts[-1] + 3_600_000 > now_ms:
        return candles_ts[:-1]
    return candles_ts

now = int(datetime(2026, 6, 15, 22, 2, 12).timestamp() * 1000)
ts = int(datetime(2026, 6, 15, 14, 15, 0).timestamp() * 1000)
print("now:", now, "ts:", ts)
print("dropped:", drop_forming([ts], now))
