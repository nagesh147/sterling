"""Cache trigger rows once, then sweep U1 and U3 over them properly."""
from __future__ import annotations
import json, math, statistics as st, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study.gamma_move._kite import pct
from study.gamma_move.step6_conjunction import levels_asof, supertrend, day

OUT = Path(__file__).parent / "out"
opt = json.loads((OUT / "bars.json").read_text())
spot = json.loads((OUT / "spot_daily.json").read_text())
BARS_PER_DAY, VOL_LOOKBACK = 25, 20

OI_K, VOL_K, PX_K = 3.0, 2.5, 2.0            # the looser set, for sample size

# ---- one pass: every trigger, with the spot index it happened on -------------
cache = Path(__file__).parent / "out" / "triggers.json"
if cache.exists():
    rows = json.loads(cache.read_text())
else:
    lvl_cache: dict[tuple[str, int], dict] = {}
    rows = []
    for sym, rec in opt.items():
        name = rec["meta"]["underlying"]
        if name not in spot:
            continue
        sb = spot[name]
        sidx = {day(b["date"]): i for i, b in enumerate(sb)}
        bars = [b for b in rec["bars"] if (b.get("oi") or 0) > 0 and (b.get("close") or 0) > 0]
        by = defaultdict(list)
        for b in bars:
            by[day(b["date"])].append(b)
        days = sorted(by)
        flat = [b for d in days for b in by[d]]
        idx = {id(b): i for i, b in enumerate(flat)}
        hist = []
        for d in days:
            seq = by[d]
            for i, b in enumerate(seq):
                prev = seq[i - 1] if i else None
                base = st.mean(hist[-VOL_LOOKBACK:]) if len(hist) >= VOL_LOOKBACK else None
                hist.append(b["volume"])
                if prev is None or not prev["oi"] or not prev["close"] or not base:
                    continue
                if not ((prev["oi"] - b["oi"]) / prev["oi"] * 100 >= OI_K
                        and b["volume"] / base >= VOL_K
                        and (b["close"] - prev["close"]) / prev["close"] * 100 >= PX_K):
                    continue
                j = idx[id(b)]
                win = flat[j + 1: j + 1 + 2 * BARS_PER_DAY]
                if len(win) < BARS_PER_DAY:
                    continue
                si = sidx.get(d)
                if si is None or si <= 40:
                    continue
                key = (name, si)
                if key not in lvl_cache:
                    lvl_cache[key] = levels_asof(sb, si)
                lv = lvl_cache[key]
                kind = "resistance" if rec["meta"]["option_type"] == "CE" else "support"
                px = sb[si - 1]["close"]
                cds = [abs(p - px) / p * 100 for p, _ in lv[kind]]
                rows.append({
                    "name": name, "si": si, "opt": rec["meta"]["option_type"],
                    "dist": min(cds) if cds else None,
                    "mfe": (max(w["high"] for w in win) - b["close"]) / b["close"] * 100,
                    "mae": (min(w["low"] for w in win) - b["close"]) / b["close"] * 100,
                })
    cache.write_text(json.dumps(rows))
print(f"cached triggers: {len(rows)} (OI>={OI_K} vol>={VOL_K} px>={PX_K})")

def rate(sel, k=30):
    return 100 * sum(1 for r in sel if r["mfe"] >= k) / len(sel) if sel else float("nan")

def wilson(hits, n, z=1.96):
    """95% CI on a hit rate. A lift with overlapping intervals is not a finding."""
    if not n: return (float("nan"), float("nan"))
    p = hits / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))

with_d = [r for r in rows if r["dist"] is not None]
print(f"with level context: {len(with_d)}\n")

print("=== U1: level proximity, with 95% CI on the MFE>=30% rate ===")
print(f"{'band':>12} {'n':>5} {'MFE>=30%':>9} {'95% CI':>16} {'medMFE':>8}")
for band in (0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0):
    sel = [r for r in with_d if r["dist"] <= band]
    h = sum(1 for r in sel if r["mfe"] >= 30)
    lo, hi = wilson(h, len(sel))
    print(f"{'<= '+str(band)+'%':>12} {len(sel):>5} {rate(sel):>8.1f}% "
          f"{f'[{lo:.1f}, {hi:.1f}]':>16} {pct([r['mfe'] for r in sel],50):>7.1f}%")
far = [r for r in with_d if r["dist"] > 3.0]
h = sum(1 for r in far if r["mfe"] >= 30); lo, hi = wilson(h, len(far))
print(f"{'> 3% (far)':>12} {len(far):>5} {rate(far):>8.1f}% {f'[{lo:.1f}, {hi:.1f}]':>16} "
      f"{pct([r['mfe'] for r in far],50):>7.1f}%")

print("\n=== U3: SuperTrend grid — does agreeing beat disagreeing? ===")
print(f"{'period':>7} {'mult':>5} | {'agree n':>8} {'agree%':>7} | {'disagree n':>11} {'disag%':>7} | {'lift':>6}")
st_cache: dict[tuple[str, int, float], list] = {}
for period in (7, 10, 14, 21):
    for mult in (2.0, 2.5, 3.0, 4.0):
        agree, disagree = [], []
        for r in with_d:
            k = (r["name"], period, mult)
            if k not in st_cache:
                st_cache[k] = supertrend(spot[r["name"]], period, mult)
            d = st_cache[k]
            reg = d[r["si"] - 1] if r["si"] - 1 < len(d) else 0
            if reg == 0:
                continue
            (agree if (reg == 1) == (r["opt"] == "CE") else disagree).append(r)
        if len(agree) < 20 or len(disagree) < 20:
            continue
        a, b = rate(agree), rate(disagree)
        print(f"{period:>7} {mult:>5.1f} | {len(agree):>8} {a:>6.1f}% | {len(disagree):>11} "
              f"{b:>6.1f}% | {a-b:>+5.1f}")
