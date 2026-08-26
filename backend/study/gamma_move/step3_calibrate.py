"""Measure what the three trigger conditions actually look like on real bars."""
from __future__ import annotations
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study.gamma_move._kite import pct

OUT = Path(__file__).parent / "out"
store = json.loads((OUT / "bars.json").read_text())

def day(iso): return iso[:10]

# ---------------------------------------------------------------- A. boundary
# Does open interest carry across a session boundary, or restate? The whole
# "phantom unwind at 09:15" guard depends on the answer, so measure it.
first_of_day, within_day = [], []
for sym, rec in store.items():
    bars = [b for b in rec["bars"] if (b.get("oi") or 0) > 0]
    for i in range(1, len(bars)):
        p, q = bars[i - 1], bars[i]
        if not p["oi"]:
            continue
        drop = (p["oi"] - q["oi"]) / p["oi"] * 100
        (first_of_day if day(p["date"]) != day(q["date"]) else within_day).append(drop)

def describe(name, xs):
    if not xs:
        print(f"{name}: (empty)"); return
    print(f"{name}: n={len(xs):>7,}  mean={st.mean(xs):+7.3f}  sd={st.pstdev(xs):6.3f}  "
          f"p50={pct(xs,50):+7.3f}  p90={pct(xs,90):+7.3f}  p99={pct(xs,99):+7.3f}  "
          f"max={max(xs):+8.2f}")

print("=== A. OI change across vs within a session boundary (percent drop) ===")
describe("  across boundary", first_of_day)
describe("  within session ", within_day)
big = lambda xs, k: 100.0 * sum(1 for x in xs if x >= k) / max(1, len(xs))
for k in (5, 10, 20):
    print(f"   >= {k}% drop:  across={big(first_of_day,k):5.2f}%   within={big(within_day,k):5.2f}%")

# ------------------------------------------------------------- B. the metrics
VOL_LOOKBACK = 20
rows = []
for sym, rec in store.items():
    bars = [b for b in rec["bars"] if (b.get("oi") or 0) > 0 and (b.get("close") or 0) > 0]
    by = defaultdict(list)
    for b in bars:
        by[day(b["date"])].append(b)
    days = sorted(by)
    hist = []                                   # rolling volume history, cross-session
    for d in days:
        seq = by[d]
        for i, b in enumerate(seq):
            prev = seq[i - 1] if i else None     # OI + price: within-session only
            base = st.mean(hist[-VOL_LOOKBACK:]) if len(hist) >= VOL_LOOKBACK else None
            hist.append(b["volume"])
            if prev is None or not prev["oi"] or not prev["close"] or base is None or base <= 0:
                continue
            rows.append({
                "sym": sym, "day": d, "i": i,
                "oi_drop_pct": (prev["oi"] - b["oi"]) / prev["oi"] * 100,
                "volume_ratio": b["volume"] / base,
                "price_gain_pct": (b["close"] - prev["close"]) / prev["close"] * 100,
                "close": b["close"], "opt": rec["meta"]["option_type"],
            })

print(f"\n=== B. evaluable bars: {len(rows):,} over {len(store)} contracts ===")
for f in ("oi_drop_pct", "volume_ratio", "price_gain_pct"):
    xs = [r[f] for r in rows]
    print(f"  {f:<15} p50={pct(xs,50):8.3f} p75={pct(xs,75):8.3f} p90={pct(xs,90):8.3f} "
          f"p95={pct(xs,95):8.3f} p99={pct(xs,99):8.3f} p99.5={pct(xs,99.5):8.3f}")

# ------------------------------------------------- C. joint rate vs thresholds
print("\n=== C. joint trigger rate (all three at once) ===")
print(f"{'oi%':>5} {'vol x':>6} {'px%':>5} | {'hits':>6} {'rate%':>7} {'per-name/day':>13}")
n_days = len({r["day"] for r in rows}) or 1
n_syms = len(store)
grid = []
for oi_k in (2.0, 3.0, 5.0, 7.5, 10.0):
    for vol_k in (1.5, 2.0, 2.5, 3.0):
        for px_k in (1.0, 2.0, 3.0, 5.0):
            hits = [r for r in rows
                    if r["oi_drop_pct"] >= oi_k and r["volume_ratio"] >= vol_k
                    and r["price_gain_pct"] >= px_k]
            grid.append((oi_k, vol_k, px_k, len(hits)))
for oi_k, vol_k, px_k, n in grid:
    if n:
        print(f"{oi_k:5.1f} {vol_k:6.1f} {px_k:5.1f} | {n:6,} {100*n/len(rows):7.4f} "
              f"{n/n_days/n_syms:13.4f}")
json.dump({"rows": len(rows), "n_days": n_days, "n_syms": n_syms, "grid": grid},
          open(OUT / "calib_b.json", "w"))
print(f"\n(sessions={n_days}, contracts={n_syms})")
