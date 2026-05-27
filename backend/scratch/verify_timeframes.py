"""Compare macro/execution timeframe pairs for the price-action scalper.

Same OOS-robust methodology as the parameter optimizer (per-symbol 70/30 time
split, ranked by held-out PF), but the swept dimension is the (structure TF,
entry TF) pair instead of the pattern params — everything else held at defaults
to isolate the timeframe effect. The engine is TF-agnostic (operates on candle
arrays), so this just feeds it different resolutions.
"""
from __future__ import annotations

import bisect
import time

import numpy as np

from app.services import ohlcv_store
from app.schemas.market import Candle
from app.engines.scalping.config import default_config
from app.engines.scalping.levels import detect_levels
from app.engines.scalping.price_action import evaluate_price_action

SYMS = ["BTC", "ETH", "SOL", "XRP"]
DAYS = 75
PAIRS = [
    ("4h", "15m"),   # current baseline
    ("4h", "30m"),
    ("4h", "5m"),
    ("2h", "15m"),
    ("2h", "30m"),
    ("1h", "15m"),
    ("1h", "5m"),
]
W_EXEC, W_MACRO = 672, 180
OOS_FRAC = 0.30
TF_MIN = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240}
STEP = {"5m": 3, "15m": 2, "30m": 1, "1h": 1}        # eval cadence per exec TF
MAXH = {"5m": 288, "15m": 96, "30m": 48, "1h": 24}   # ~1 trading day of exec bars

_DATA: dict = {}


def _load(sym, res, days):
    rows = ohlcv_store.get_candles(f"{sym}USD", res, limit=500_000, since=int(time.time()) - days * 86_400)
    return [Candle(timestamp_ms=int(r["time"]) * 1000, open=r["open"], high=r["high"],
                   low=r["low"], close=r["close"], volume=r["volume"]) for r in rows]


def _exit_fixed(cE, i, is_long, entry, sl, tp, maxh):
    for k in range(i + 1, min(i + 1 + maxh, len(cE))):
        hi, lo = cE[k].high, cE[k].low
        if is_long:
            if lo <= sl: return sl, k
            if hi >= tp: return tp, k
        else:
            if hi >= sl: return sl, k
            if lo <= tp: return tp, k
    j = min(i + maxh, len(cE) - 1)
    return cE[j].close, j


def _replay(sym, macro, execr, cfg):
    cM, cE = _DATA[sym][macro], _DATA[sym][execr]
    if len(cE) < W_EXEC + 50 or len(cM) < W_MACRO + 5:
        return [], 0
    tsM = [c.timestamp_ms for c in cM]
    step = STEP.get(execr, 2)
    maxh = MAXH.get(execr, 96)
    out, cooldown, cj, levels = [], -1, -1, []
    n = len(cE)
    i = W_EXEC
    while i < n - 1:
        if i <= cooldown:
            i += step; continue
        j = bisect.bisect_right(tsM, cE[i].timestamp_ms)
        if j < W_MACRO:
            i += step; continue
        if j != cj:
            cw = cM[j - W_MACRO:j]
            levels = detect_levels(
                np.array([c.high for c in cw]), np.array([c.low for c in cw]),
                np.array([c.close for c in cw]), np.array([c.timestamp_ms for c in cw], dtype=np.int64), cfg)
            cj = j
        sig = evaluate_price_action(sym, cM[j - W_MACRO:j], cE[i - W_EXEC:i + 1], levels, cfg)
        if sig.entry_ok and sig.entry and sig.stop_loss and sig.take_profit:
            is_long = sig.direction == "long"
            ex, ck = _exit_fixed(cE, i, is_long, sig.entry, sig.stop_loss, sig.take_profit, maxh)
            out.append((i, (1 if is_long else -1) * (ex - sig.entry) / abs(sig.entry - sig.stop_loss)))
            cooldown = ck
        i += step
    return out, n


def _pf_exp(trades):
    n = len(trades)
    if not n:
        return 0.0, 0.0, 0
    wins = sum(t for t in trades if t > 0)
    loss = abs(sum(t for t in trades if t <= 0))
    pf = (wins / loss) if loss > 0 else (999.0 if wins > 0 else 0.0)
    return round(pf, 2), round(sum(trades) / n, 3), n


def main():
    cfg = default_config()
    needed = set()
    for m, e in PAIRS:
        needed.add(m); needed.add(e)
    for s in SYMS:
        _DATA[s] = {}
        for res in needed:
            extra = 60 if TF_MIN[res] >= 120 else 20
            _DATA[s][res] = _load(s, res, DAYS + extra)
    print(f"Universe {SYMS} · {DAYS}d · params at defaults (cb3/tol0.5/rr1.5/trend off)\n")
    print(f"  {'macro/exec':12} {'OOSpf':>6} {'OOSexp':>7} {'nOOS':>5}  {'ISpf':>6} {'ISexp':>7} {'nIS':>5}")
    rows = []
    for macro, execr in PAIRS:
        is_t, oos_t = [], []
        for s in SYMS:
            sigs, n = _replay(s, macro, execr, cfg)
            if not n:
                continue
            split = int(W_EXEC + (n - W_EXEC) * (1 - OOS_FRAC))
            for (i, pnl) in sigs:
                (oos_t if i >= split else is_t).append(pnl)
        opf, oexp, no = _pf_exp(oos_t)
        ipf, iexp, ni = _pf_exp(is_t)
        rows.append((f"{macro}/{execr}", opf, oexp, no, ipf, iexp, ni))
    for r in sorted(rows, key=lambda x: x[1], reverse=True):
        tag = "  <- baseline" if r[0] == "4h/15m" else ""
        print(f"  {r[0]:12} {r[1]:>6} {r[2]:>7} {r[3]:>5}  {r[4]:>6} {r[5]:>7} {r[6]:>5}{tag}")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\n({time.time()-t0:.0f}s)")
