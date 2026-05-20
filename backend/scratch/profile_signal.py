import time
from evidence_report import build_universe
from app.engines.directional.signal_engine import compute_signal, _to_vwap_candles
import numpy as np

c1h, c4h, rlabels = build_universe(seed=42, n_total=2000)
c1 = c1h[200:401]

t_total = 0.0
t_inputs = 0.0
t_ha = 0.0
t_st1 = 0.0
t_st2 = 0.0
t_vwap_candles = 0.0
t_st3 = 0.0
t_other = 0.0

from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend

for _ in range(1000):
    t0 = time.time()
    o = np.array([c.open for c in c1], dtype=np.float64)
    h = np.array([c.high for c in c1], dtype=np.float64)
    l = np.array([c.low for c in c1], dtype=np.float64)
    c = np.array([c.close for c in c1], dtype=np.float64)
    volume = np.array([candle.volume for candle in c1], dtype=np.float64)
    t1 = time.time()
    
    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)
    t2 = time.time()
    
    st1_line, st1_trend = compute_supertrend(ha_h, ha_l, ha_c, 7, 3.0)
    t3 = time.time()
    
    st2_line, st2_trend = compute_supertrend(h, l, c, 14, 2.0)
    t4 = time.time()
    
    vwap_candles = list(_to_vwap_candles(c1))
    vwap_h = np.array([v.high for v in vwap_candles], dtype=np.float64)
    vwap_l = np.array([v.low for v in vwap_candles], dtype=np.float64)
    vwap_c = np.array([v.close for v in vwap_candles], dtype=np.float64)
    t5 = time.time()
    
    st3_line, st3_trend = compute_supertrend(vwap_h, vwap_l, vwap_c, 21, 2.0)
    t6 = time.time()
    
    # Rest of compute_signal
    # ... we will just measure it
    
    t_inputs += t1 - t0
    t_ha += t2 - t1
    t_st1 += t3 - t2
    t_st2 += t4 - t3
    t_vwap_candles += t5 - t4
    t_st3 += t6 - t5

print(f"Inputs conversion: {t_inputs*1000:.2f}ms")
print(f"Heikin Ashi: {t_ha*1000:.2f}ms")
print(f"SuperTrend 1: {t_st1*1000:.2f}ms")
print(f"SuperTrend 2: {t_st2*1000:.2f}ms")
print(f"VWAP Candles parsing: {t_vwap_candles*1000:.2f}ms")
print(f"SuperTrend 3: {t_st3*1000:.2f}ms")
