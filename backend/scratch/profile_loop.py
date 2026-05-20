import time
import bisect
import numpy as np
from evidence_report import build_universe
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup

c1h, c4h, rlabels = build_universe(seed=42, n_total=26280)
n1h, n4h = len(c1h), len(c4h)
c4h_ts = [c.timestamp_ms for c in c4h]

MIN_1H = 30
_4H_MS = 4 * 3_600_000

# Benchmark parts
t_slice = 0.0
t_reg = 0.0
t_sig = 0.0
t_stp = 0.0

for i in range(MIN_1H, MIN_1H + 200):
    t0 = time.time()
    ts = c1h[i].timestamp_ms
    idx_c4 = bisect.bisect_right(c4h_ts, ts - _4H_MS)
    c4 = c4h[:idx_c4]
    c1 = c1h[max(0, i - 200): i + 1]
    t1 = time.time()
    reg = compute_regime(c4)
    t2 = time.time()
    sig = compute_signal(c1)
    t3 = time.time()
    stp = evaluate_setup(reg, sig)
    t4 = time.time()
    
    t_slice += t1 - t0
    t_reg += t2 - t1
    t_sig += t3 - t2
    t_stp += t4 - t3

print(f"Slice time: {t_slice*1000:.2f}ms")
print(f"Regime time: {t_reg*1000:.2f}ms")
print(f"Signal time: {t_sig*1000:.2f}ms")
print(f"Setup time: {t_stp*1000:.2f}ms")
