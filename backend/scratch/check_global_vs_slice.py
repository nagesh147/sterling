import numpy as np
from evidence_report import build_universe
from app.engines.indicators.supertrend import compute_supertrend
from app.engines.indicators.heikin_ashi import compute_heikin_ashi

c1h, c4h, rlabels = build_universe(seed=42, n_total=1000)
o = np.array([c.open for c in c1h], dtype=np.float64)
h = np.array([c.high for c in c1h], dtype=np.float64)
l = np.array([c.low for c in c1h], dtype=np.float64)
c = np.array([c.close for c in c1h], dtype=np.float64)

# Global calculation
ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)
g_st_line, g_st_trend = compute_supertrend(ha_h, ha_l, ha_c, 7, 3.0)

# Slice calculation at index i
matches = 0
total = 0
for i in range(200, 1000):
    o_s = o[i-200 : i+1]
    h_s = h[i-200 : i+1]
    l_s = l[i-200 : i+1]
    c_s = c[i-200 : i+1]
    
    ha_o_s, ha_h_s, ha_l_s, ha_c_s = compute_heikin_ashi(o_s, h_s, l_s, c_s)
    s_st_line, s_st_trend = compute_supertrend(ha_h_s, ha_l_s, ha_c_s, 7, 3.0)
    
    total += 1
    if g_st_trend[i] == s_st_trend[-1] and abs(g_st_line[i] - s_st_line[-1]) < 1e-5:
        matches += 1

print(f"Matches: {matches} / {total} ({matches/total*100:.2f}%)")
