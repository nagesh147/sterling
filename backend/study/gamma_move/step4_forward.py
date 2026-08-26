"""Do the three conditions predict a move, or just describe a busy bar?

For every evaluable bar, record the forward excursion of the option premium over
the next 1 and 2 sessions, then compare the triggered population against the
unconditional one. A threshold that only makes signals rarer is not calibration.
"""
from __future__ import annotations
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study.gamma_move._kite import pct

OUT = Path(__file__).parent / "out"
store = json.loads((OUT / "bars.json").read_text())
BARS_PER_DAY, VOL_LOOKBACK = 25, 20
def day(iso): return iso[:10]

rows = []
for sym, rec in store.items():
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
            j = idx[id(b)]
            fwd = {}
            for horizon, n in (("d1", BARS_PER_DAY), ("d2", 2 * BARS_PER_DAY)):
                win = flat[j + 1: j + 1 + n]
                if len(win) < n // 2:
                    fwd[horizon] = None
                    continue
                hi = max(w["high"] for w in win); lo = min(w["low"] for w in win)
                fwd[horizon] = {"mfe": (hi - b["close"]) / b["close"] * 100,
                                "mae": (lo - b["close"]) / b["close"] * 100}
            rows.append({
                "oi": (prev["oi"] - b["oi"]) / prev["oi"] * 100,
                "vol": b["volume"] / base,
                "px": (b["close"] - prev["close"]) / prev["close"] * 100,
                "fwd": fwd, "opt": rec["meta"]["option_type"],
            })

def summarise(label, sel, horizon="d1"):
    xs = [r["fwd"][horizon] for r in sel if r["fwd"].get(horizon)]
    if len(xs) < 12:
        print(f"  {label:<34} n={len(xs):<5} (too few)"); return None
    mfe = [x["mfe"] for x in xs]; mae = [x["mae"] for x in xs]
    # A gamma move is a large favourable excursion, so the useful statistic is
    # how often MFE clears a real multiple -- not the mean, which one 400% bar
    # can carry on its own.
    hit30 = 100 * sum(1 for m in mfe if m >= 30) / len(mfe)
    hit50 = 100 * sum(1 for m in mfe if m >= 50) / len(mfe)
    hit100 = 100 * sum(1 for m in mfe if m >= 100) / len(mfe)
    print(f"  {label:<34} n={len(xs):<5} medMFE={pct(mfe,50):6.1f}% medMAE={pct(mae,50):6.1f}%  "
          f"MFE>=30%:{hit30:5.1f}  >=50%:{hit50:5.1f}  >=100%:{hit100:5.1f}")
    return {"n": len(xs), "hit30": hit30, "hit50": hit50, "hit100": hit100,
            "medMFE": pct(mfe, 50), "medMAE": pct(mae, 50)}

print(f"evaluable bars: {len(rows):,}\n")
for h in ("d1", "d2"):
    print(f"=== forward horizon {h} ===")
    base = summarise("ALL BARS (baseline)", rows, h)
    print("  --- one condition at a time ---")
    summarise("OI drop >= 5% only", [r for r in rows if r["oi"] >= 5], h)
    summarise("volume >= 3x only", [r for r in rows if r["vol"] >= 3], h)
    summarise("price gain >= 3% only", [r for r in rows if r["px"] >= 3], h)
    print("  --- pairs ---")
    summarise("volume>=3x AND price>=3%", [r for r in rows if r["vol"] >= 3 and r["px"] >= 3], h)
    summarise("OI>=5% AND price>=3%", [r for r in rows if r["oi"] >= 5 and r["px"] >= 3], h)
    print("  --- the full triple, by strictness ---")
    for oi_k, v_k, p_k in ((2, 2, 2), (3, 2.5, 2), (3, 3, 3), (5, 3, 3), (5, 4, 3), (7.5, 3, 3)):
        summarise(f"OI>={oi_k}% vol>={v_k}x px>={p_k}%",
                  [r for r in rows if r["oi"] >= oi_k and r["vol"] >= v_k and r["px"] >= p_k], h)
    print()
