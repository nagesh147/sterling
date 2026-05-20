import time
import numpy as np
from app.schemas.market import Candle
from app.engines.indicators.supertrend import compute_supertrend

# Create 200 candles
candles = [Candle(timestamp_ms=1700000000000 + i * 3600000, open=1.0, high=2.0, low=0.5, close=1.5, volume=100.0) for i in range(200)]
h = np.array([c.high for c in candles], dtype=np.float64)
l = np.array([c.low for c in candles], dtype=np.float64)
c = np.array([c.close for c in candles], dtype=np.float64)
volume = np.array([c.volume for c in candles], dtype=np.float64)

# Original
def original_vwap(c1):
    from app.engines.directional.signal_engine import _to_vwap_candles
    vwap_candles = list(_to_vwap_candles(c1))
    vwap_h = np.array([v.high for v in vwap_candles], dtype=np.float64)
    vwap_l = np.array([v.low for v in vwap_candles], dtype=np.float64)
    vwap_c = np.array([v.close for v in vwap_candles], dtype=np.float64)
    return vwap_h, vwap_l, vwap_c

# Optimized
def optimized_vwap(c1, h, l, c, volume):
    n_c = len(c1)
    vwap_h = np.zeros(n_c, dtype=np.float64)
    vwap_l = np.zeros(n_c, dtype=np.float64)
    vwap_c = np.zeros(n_c, dtype=np.float64)
    
    sessions = {}
    for idx in range(n_c):
        cand = c1[idx]
        day_key = cand.timestamp_ms // 86_400_000
        if day_key not in sessions:
            sessions[day_key] = {"cum_pv": 0.0, "cum_vol": 0.0}
        typical = (h[idx] + l[idx] + c[idx]) / 3.0
        sessions[day_key]["cum_pv"] += typical * volume[idx]
        sessions[day_key]["cum_vol"] += volume[idx]
        vwap = (
            sessions[day_key]["cum_pv"] / sessions[day_key]["cum_vol"]
            if sessions[day_key]["cum_vol"] > 0
            else c[idx]
        )
        offset = vwap - c[idx]
        vwap_h[idx] = h[idx] + offset
        vwap_l[idx] = l[idx] + offset
        vwap_c[idx] = vwap
    return vwap_h, vwap_l, vwap_c

start = time.time()
for _ in range(5000):
    vh1, vl1, vc1 = original_vwap(candles)
print("Original:", time.time() - start)

start = time.time()
for _ in range(5000):
    vh2, vl2, vc2 = optimized_vwap(candles, h, l, c, volume)
print("Optimized:", time.time() - start)
