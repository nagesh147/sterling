import time
import bisect
import numpy as np
from evidence_report import build_universe
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup

print("Generating universe...")
c1h, c4h, rlabels = build_universe(seed=42, n_total=26280)
n1h, n4h = len(c1h), len(c4h)
c4h_ts = [c.timestamp_ms for c in c4h]

print("Starting benchmark of 1000 iterations...")
start_time = time.time()
MIN_1H = 30
MIN_4H = 55
_4H_MS = 4 * 3_600_000

for i in range(MIN_1H, MIN_1H + 1000):
    ts = c1h[i].timestamp_ms
    idx_c4 = bisect.bisect_right(c4h_ts, ts - _4H_MS)
    c4 = c4h[:idx_c4]
    c1 = c1h[max(0, i - 200): i + 1]
    reg = compute_regime(c4)
    sig = compute_signal(c1)
    stp = evaluate_setup(reg, sig)

elapsed = time.time() - start_time
print(f"Time for 1000 iterations: {elapsed:.2f} seconds")
print(f"Estimated time for 26280 iterations: {elapsed * 26.28:.2f} seconds")
