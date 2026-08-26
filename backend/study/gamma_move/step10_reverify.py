"""Re-run the U1 sweep through the SHIPPED find_levels, after the pivot fix.

The original sweep used the study's own level code. Fixing the plateau bug in
the engine changed the measuring instrument, so the number has to be re-taken
with the instrument that actually ships or it is a number about dead code.
"""
from __future__ import annotations
import json, math, statistics as st, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.engines.gamma_move import Candle, GammaMoveConfig, find_levels, live_levels
from study.gamma_move._kite import pct

OUT = Path(__file__).parent / "out"
opt = json.loads((OUT / "bars.json").read_text())
spot = json.loads((OUT / "spot_daily.json").read_text())
cfg = GammaMoveConfig()
BARS_PER_DAY, VOL_LOOKBACK = 25, 20
OI_K, VOL_K, PX_K = cfg.min_oi_drop_pct, cfg.volume_spike_mult, cfg.min_price_gain_pct
def day(iso): return iso[:10]
def ms(iso): return int(datetime.fromisoformat(iso).timestamp() * 1000)


def wilson(h, n, z=1.96):
    if not n: return (float("nan"),) * 2
    p = h / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - w), 100 * (c + w))


lvl_cache = {}
rows, baseline = [], []
for sym, rec in opt.items():
    name = rec["meta"]["underlying"]
    if name not in spot:
        continue
    sb = [Candle(ts_ms=ms(b["date"]), open=b["open"], high=b["high"], low=b["low"],
                 close=b["close"]) for b in spot[name]]
    sidx = {day(b["date"]): i for i, b in enumerate(spot[name])}
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
            j = idx[id(b)]
            win = flat[j + 1: j + 1 + 2 * BARS_PER_DAY]
            if len(win) < BARS_PER_DAY:
                continue
            mfe = (max(w["high"] for w in win) - b["close"]) / b["close"] * 100
            baseline.append(mfe)
            if prev is None or not prev["oi"] or not prev["close"] or not base:
                continue
            if not ((prev["oi"] - b["oi"]) / prev["oi"] * 100 >= OI_K
                    and b["volume"] / base >= VOL_K
                    and (b["close"] - prev["close"]) / prev["close"] * 100 >= PX_K):
                continue
            si = sidx.get(d)
            if si is None or si <= 40:
                continue
            key = (name, si)
            if key not in lvl_cache:
                # Exactly what the engine does, on bars knowable at si.
                lvl_cache[key] = find_levels(
                    sb[:si], pivot_lookback=cfg.pivot_lookback,
                    cluster_pct=cfg.level_cluster_pct,
                    min_touches=cfg.min_level_touches, window=cfg.level_lookback_days)
            lv = lvl_cache[key]
            kind = "resistance" if rec["meta"]["option_type"] == "CE" else "support"
            px = sb[si - 1].close
            cands = [l.distance_pct(px) for l in lv if l.kind == kind]
            rows.append({"dist": min(cands) if cands else None, "mfe": mfe})

with_d = [r for r in rows if r["dist"] is not None]
h = sum(1 for m in baseline if m >= 30); lo, hi = wilson(h, len(baseline))
print(f"baseline                 n={len(baseline):<7} MFE>=30%: {100*h/len(baseline):5.1f}% [{lo:.1f}, {hi:.1f}]")
h = sum(1 for r in rows if r["mfe"] >= 30); lo, hi = wilson(h, len(rows))
print(f"trigger only             n={len(rows):<7} MFE>=30%: {100*h/len(rows):5.1f}% [{lo:.1f}, {hi:.1f}]")
print(f"\n{'band':>10} {'n':>5} {'MFE>=30%':>9} {'95% CI':>16}")
for band in (0.75, 1.0, 1.5, 2.0, 3.0):
    sel = [r for r in with_d if r["dist"] <= band]
    if not sel: continue
    h = sum(1 for r in sel if r["mfe"] >= 30); lo, hi = wilson(h, len(sel))
    print(f"{'<= '+str(band)+'%':>10} {len(sel):>5} {100*h/len(sel):>8.1f}% {f'[{lo:.1f}, {hi:.1f}]':>16}")
far = [r for r in with_d if r["dist"] > 3.0]
h = sum(1 for r in far if r["mfe"] >= 30); lo, hi = wilson(h, len(far))
print(f"{'> 3% far':>10} {len(far):>5} {100*h/len(far):>8.1f}% {f'[{lo:.1f}, {hi:.1f}]':>16}")
