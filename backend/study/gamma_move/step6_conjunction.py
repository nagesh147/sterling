"""U1 + U3, and the question that matters: does the level filter rescue the trigger?

Levels are built strictly from bars that had already closed AND whose pivot was
already confirmable on the day being judged. A pivot at bar i is not knowable
until bar i+L, so using it on day i is lookahead -- the exact failure this
codebase has had to strip out of a backtest before.
"""
from __future__ import annotations
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study.gamma_move._kite import pct

OUT = Path(__file__).parent / "out"
opt = json.loads((OUT / "bars.json").read_text())
spot = json.loads((OUT / "spot_daily.json").read_text())
BARS_PER_DAY, VOL_LOOKBACK = 25, 20
def day(iso): return iso[:10]


# ---------------------------------------------------------------- levels
def levels_asof(bars, upto_idx, *, lookback=5, cluster_pct=0.75, min_touches=2,
                window=120):
    """Clustered swing levels knowable at bar `upto_idx`, exclusive."""
    lo = max(0, upto_idx - window)
    piv = {"resistance": [], "support": []}
    # a pivot at i needs `lookback` bars of confirmation, so stop that far back
    for i in range(lo + lookback, upto_idx - lookback):
        seg = bars[i - lookback:i + lookback + 1]
        if bars[i]["high"] >= max(s["high"] for s in seg):
            piv["resistance"].append(bars[i]["high"])
        if bars[i]["low"] <= min(s["low"] for s in seg):
            piv["support"].append(bars[i]["low"])
    out = {}
    for kind, ps in piv.items():
        clusters = []
        for p in sorted(ps):
            if clusters and abs(p - clusters[-1][-1]) / clusters[-1][-1] * 100 <= cluster_pct:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        out[kind] = [(st.mean(cl), len(cl)) for cl in clusters if len(cl) >= min_touches]
    return out


def supertrend(bars, period=10, mult=3.0):
    """Direction per bar: +1 up, -1 down. Standard ATR-band formulation."""
    if len(bars) < period + 2:
        return []
    tr, atr, dirs = [], [], []
    prev_close = bars[0]["close"]
    for b in bars:
        tr.append(max(b["high"] - b["low"], abs(b["high"] - prev_close),
                      abs(b["low"] - prev_close)))
        prev_close = b["close"]
    run = None
    fub = flb = None
    d = 1
    for i, b in enumerate(bars):
        if i < period:
            atr.append(None); dirs.append(0); continue
        run = st.mean(tr[i - period + 1:i + 1]) if run is None else (run * (period - 1) + tr[i]) / period
        atr.append(run)
        mid = (b["high"] + b["low"]) / 2
        ub, lb = mid + mult * run, mid - mult * run
        pc = bars[i - 1]["close"]
        fub = ub if (fub is None or ub < fub or pc > fub) else fub
        flb = lb if (flb is None or lb > flb or pc < flb) else flb
        if d == 1 and b["close"] < flb: d = -1
        elif d == -1 and b["close"] > fub: d = 1
        dirs.append(d)
    return dirs


# ------------------------------------------------- trigger rows + level context
def trigger_rows(oi_k, vol_k, px_k):
    rows = []
    for sym, rec in opt.items():
        name = rec["meta"]["underlying"]
        if name not in spot:
            continue
        sb = spot[name]
        sidx = {day(b["date"]): i for i, b in enumerate(sb)}
        std = {p: supertrend(sb, p, m) for p, m in [(10, 3.0)]}
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
                if not ((prev["oi"] - b["oi"]) / prev["oi"] * 100 >= oi_k
                        and b["volume"] / base >= vol_k
                        and (b["close"] - prev["close"]) / prev["close"] * 100 >= px_k):
                    continue
                j = idx[id(b)]
                win = flat[j + 1: j + 1 + 2 * BARS_PER_DAY]
                if len(win) < BARS_PER_DAY:
                    continue
                mfe = (max(w["high"] for w in win) - b["close"]) / b["close"] * 100
                mae = (min(w["low"] for w in win) - b["close"]) / b["close"] * 100

                si = sidx.get(d)
                dist, regime = None, 0
                if si is not None and si > 40:
                    lv = levels_asof(sb, si)
                    kind = "resistance" if rec["meta"]["option_type"] == "CE" else "support"
                    px = sb[si - 1]["close"]
                    cands = [abs(p - px) / p * 100 for p, _ in lv[kind]]
                    dist = min(cands) if cands else None
                    dd = std[10]
                    regime = dd[si - 1] if si - 1 < len(dd) else 0
                rows.append({"mfe": mfe, "mae": mae, "dist": dist, "regime": regime,
                             "opt": rec["meta"]["option_type"]})
    return rows


def report(label, sel):
    if len(sel) < 15:
        print(f"  {label:<40} n={len(sel):<5} (too few)"); return
    mfe = [r["mfe"] for r in sel]
    print(f"  {label:<40} n={len(sel):<5} medMFE={pct(mfe,50):6.1f}%  "
          f">=30%:{100*sum(1 for m in mfe if m>=30)/len(mfe):5.1f}  "
          f">=50%:{100*sum(1 for m in mfe if m>=50)/len(mfe):5.1f}  "
          f">=100%:{100*sum(1 for m in mfe if m>=100)/len(mfe):5.1f}")


for thr in ((3.0, 2.5, 2.0), (5.0, 3.0, 3.0)):
    rows = trigger_rows(*thr)
    with_d = [r for r in rows if r["dist"] is not None]
    print(f"\n=== trigger OI>={thr[0]}% vol>={thr[1]}x px>={thr[2]}%  "
          f"(n={len(rows)}, with level context={len(with_d)}) ===")
    report("all triggers", rows)
    print("  --- U1: by distance to the matching level ---")
    for band in (0.5, 1.0, 1.5, 2.0, 3.0, 5.0):
        report(f"spot within {band}% of level", [r for r in with_d if r["dist"] <= band])
    report("spot MORE than 3% from level", [r for r in with_d if r["dist"] > 3.0])
    print("  --- U3: SuperTrend(10, 3.0) agreement ---")
    report("regime agrees with direction",
           [r for r in with_d if (r["regime"] == 1) == (r["opt"] == "CE") and r["regime"] != 0])
    report("regime disagrees",
           [r for r in with_d if r["regime"] != 0 and (r["regime"] == 1) != (r["opt"] == "CE")])
    print("  --- both filters together ---")
    report("within 1.5% of level AND regime agrees",
           [r for r in with_d if r["dist"] <= 1.5 and r["regime"] != 0
            and (r["regime"] == 1) == (r["opt"] == "CE")])
