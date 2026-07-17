"""Generate a golden fixture from the BACKEND engine indicators so the frontend
can assert byte-for-byte parity. Input OHLC is fully deterministic (no RNG) so the
same series can be reproduced anywhere."""
import json, math, sys
sys.path.insert(0, "/home/nageshmadaram/Sterling/backend")
import numpy as np
from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend

N = 300
# Deterministic pseudo-market series: trend + multi-freq waves + a bounded
# "noise" term from a fixed integer hash (reproducible in JS if ever needed).
o = []; h = []; l = []; c = []
price = 100.0
for i in range(N):
    drift = 0.03 * math.sin(i / 23.0) + 0.015 * math.sin(i / 7.0)
    wig = 0.4 * math.sin(i / 3.0) + 0.25 * math.cos(i / 11.0)
    close = 100.0 + 8.0 * math.sin(i / 19.0) + 4.0 * math.sin(i / 5.0) + drift * i * 0.05
    open_ = close - wig
    high = max(open_, close) + 0.6 + 0.3 * abs(math.sin(i / 2.0))
    low = min(open_, close) - 0.6 - 0.3 * abs(math.cos(i / 2.0))
    o.append(round(open_, 4)); c.append(round(close, 4))
    h.append(round(high, 4)); l.append(round(low, 4))

O, H, L, C = map(lambda a: np.array(a, float), (o, h, l, c))
ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(O, H, L, C)

configs = {"fast": (21, 1.0), "mid": (14, 2.0), "slow": (7, 3.0)}
st = {}
for name, (p, m) in configs.items():
    line, trend = compute_supertrend(ha_h, ha_l, ha_c, p, m)
    st[name] = {
        "period": p, "mult": m,
        "dir": ["up" if t == 1 else "down" if t == -1 else "flat" for t in trend.tolist()],
        "value": [round(float(v), 6) for v in line.tolist()],
    }

fixture = {
    "warmup": 21,
    "candles": [{"open": o[i], "high": h[i], "low": l[i], "close": c[i]} for i in range(N)],
    "ha": {
        "open": [round(float(x), 6) for x in ha_o.tolist()],
        "high": [round(float(x), 6) for x in ha_h.tolist()],
        "low": [round(float(x), 6) for x in ha_l.tolist()],
        "close": [round(float(x), 6) for x in ha_c.tolist()],
    },
    "supertrend": st,
}
out = "/home/nageshmadaram/Sterling/frontend/src/utils/__fixtures__/supertrend_parity.json"
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as f:
    json.dump(fixture, f, indent=0)
print("wrote", out, "N=", N)
# quick sanity: how many direction flips (must be non-trivial to be a real test)
for name in configs:
    d = st[name]["dir"][21:]
    flips = sum(1 for i in range(1, len(d)) if d[i] != d[i-1])
    print(name, "flips:", flips)
