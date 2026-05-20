import time
from app.schemas.market import Candle

# Create 200 candles
candles = [Candle(timestamp_ms=i, open=1.0, high=2.0, low=0.5, close=1.5, volume=100.0) for i in range(200)]

# Benchmark 1: c.open
start = time.time()
for _ in range(5000):
    o = [c.open for c in candles]
    h = [c.high for c in candles]
    l = [c.low for c in candles]
    c = [c.close for c in candles]
print("Direct access:", time.time() - start)

# Benchmark 2: c.__dict__['open']
start = time.time()
for _ in range(5000):
    o = [c.__dict__['open'] for c in candles]
    h = [c.__dict__['high'] for c in candles]
    l = [c.__dict__['low'] for c in candles]
    c = [c.__dict__['close'] for c in candles]
print("__dict__ access:", time.time() - start)
