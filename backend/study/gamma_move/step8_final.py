"""The calibrated stack vs the unconditional population. This is the number."""
from __future__ import annotations
import json, math, statistics as st, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study.gamma_move._kite import pct
from study.gamma_move.step6_conjunction import supertrend, day

OUT = Path(__file__).parent / "out"
rows = json.loads((OUT / "triggers.json").read_text())
spot = json.loads((OUT / "spot_daily.json").read_text())
opt = json.loads((OUT / "bars.json").read_text())
BARS_PER_DAY, VOL_LOOKBACK = 25, 20

PROXIMITY, ST_PERIOD, ST_MULT = 1.0, 10, 2.0


def wilson(h, n, z=1.96):
    if not n: return (float("nan"),) * 2
    p = h / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - w), 100 * (c + w))


def line(label, mfes):
    n = len(mfes)
    if n < 10:
        print(f"  {label:<44} n={n:<6} (too few)"); return
    h30 = sum(1 for m in mfes if m >= 30); h50 = sum(1 for m in mfes if m >= 50)
    l30, u30 = wilson(h30, n); l50, u50 = wilson(h50, n)
    print(f"  {label:<44} n={n:<6} medMFE={pct(mfes,50):6.1f}%  "
          f">=30%: {100*h30/n:5.1f} [{l30:4.1f},{u30:4.1f}]   "
          f">=50%: {100*h50/n:5.1f} [{l50:4.1f},{u50:4.1f}]")


# --- unconditional baseline over the same contracts and window ---------------
base = []
for sym, rec in opt.items():
    bars = [b for b in rec["bars"] if (b.get("oi") or 0) > 0 and (b.get("close") or 0) > 0]
    by = defaultdict(list)
    for b in bars:
        by[day(b["date"])].append(b)
    flat = [b for d in sorted(by) for b in by[d]]
    for j, b in enumerate(flat):
        win = flat[j + 1: j + 1 + 2 * BARS_PER_DAY]
        if len(win) < BARS_PER_DAY:
            continue
        base.append((max(w["high"] for w in win) - b["close"]) / b["close"] * 100)

stc: dict[str, list] = {}
def regime(r):
    if r["name"] not in stc:
        stc[r["name"]] = supertrend(spot[r["name"]], ST_PERIOD, ST_MULT)
    d = stc[r["name"]]
    return d[r["si"] - 1] if r["si"] - 1 < len(d) else 0

near = [r for r in rows if r["dist"] is not None and r["dist"] <= PROXIMITY]
final = [r for r in near if regime(r) != 0 and (regime(r) == 1) == (r["opt"] == "CE")]

print(f"=== forward MFE over the next 2 sessions, {len(opt)} contracts ===\n")
line("baseline: every bar, no filter", base)
line("trigger only (OI>=3% vol>=2.5x px>=2%)", [r["mfe"] for r in rows])
line(f"+ level filter (spot within {PROXIMITY}%)", [r["mfe"] for r in near])
line(f"+ SuperTrend({ST_PERIOD},{ST_MULT}) agreeing  = FULL STACK",
     [r["mfe"] for r in final])
print()
mae = [r["mae"] for r in final]
if mae:
    print(f"  full stack adverse excursion: medMAE={pct(mae,50):.1f}%  "
          f"p10={pct(mae,10):.1f}%  worst={min(mae):.1f}%")
    # R9's stop is the option's own swing low; this is what a percent stop must survive.
    for s in (20, 30, 40):
        print(f"    a {s}% stop would have been hit in "
              f"{100*sum(1 for m in mae if m <= -s)/len(mae):.0f}% of them")
print(f"\n  signals: {len(final)} over {len({r['name'] for r in final})} names "
      f"in ~{len({r['si'] for r in final})} sessions")
