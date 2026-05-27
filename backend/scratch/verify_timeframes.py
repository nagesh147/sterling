"""Full-metric macro/execution timeframe study for the price-action scalper.

3 macro × 3 execution timeframes, OOS-robust (per-symbol 70/30 time split), params
at defaults to isolate the timeframe effect. Reports win rate, profit factor,
per-trade Sharpe (mean/std of R), expectancy, total R, and max drawdown — for the
held-out (OOS) sample, plus IS PF for an overfit check. Engine is TF-agnostic.
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

SYMS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "LINK"]
DAYS = 60
MACROS = ["4h", "2h", "1h"]
EXECS = ["30m", "15m", "5m"]
W_EXEC, W_MACRO = 672, 180
OOS_FRAC = 0.30
TF_MIN = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240}
STEP = {"5m": 6, "15m": 2, "30m": 1, "1h": 1}
MAXH = {"5m": 288, "15m": 96, "30m": 48, "1h": 24}

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
    step, maxh = STEP.get(execr, 2), MAXH.get(execr, 96)
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


def _metrics(trades):
    n = len(trades)
    if not n:
        return dict(n=0, win=0.0, pf=0.0, sharpe=0.0, exp=0.0, total=0.0, dd=0.0)
    a = np.array(trades, dtype=np.float64)
    gw = a[a > 0].sum()
    gl = abs(a[a <= 0].sum())
    pf = gw / gl if gl > 0 else (999.0 if gw > 0 else 0.0)
    sharpe = float(a.mean() / a.std()) if a.std() > 1e-9 else 0.0
    eq = np.cumsum(a)
    dd = float((np.maximum.accumulate(eq) - eq).max())
    return dict(n=n, win=round(len(a[a > 0]) / n * 100, 1), pf=round(float(pf), 2),
                sharpe=round(sharpe, 2), exp=round(float(a.mean()), 3),
                total=round(float(a.sum()), 1), dd=round(dd, 1))


def main():
    cfg = default_config()
    for s in SYMS:
        _DATA[s] = {}
        for res in set(MACROS) | set(EXECS):
            extra = 60 if TF_MIN[res] >= 120 else 20
            _DATA[s][res] = _load(s, res, DAYS + extra)

    print(f"Universe {SYMS} · {DAYS}d · defaults (cb3/tol0.5/rr1.5/trend off) · OOS=last 30% by time")
    print(f"Sharpe = per-trade mean(R)/std(R). Fixed SL/TP exit, no fees/slippage.\n")
    hdr = f"  {'macro/exec':11} | {'win%':>5} {'PF':>5} {'Shrp':>5} {'expR':>6} {'totR':>6} {'ddR':>5} {'nOOS':>5} | {'IS PF':>5} {'nIS':>5}"
    print(hdr); print("  " + "-" * (len(hdr) - 2))

    rows = []
    for macro in MACROS:
        for execr in EXECS:
            is_t, oos_t = [], []
            for s in SYMS:
                sigs, n = _replay(s, macro, execr, cfg)
                if not n:
                    continue
                split = int(W_EXEC + (n - W_EXEC) * (1 - OOS_FRAC))
                for (i, pnl) in sigs:
                    (oos_t if i >= split else is_t).append(pnl)
            o, isr = _metrics(oos_t), _metrics(is_t)
            rows.append((f"{macro}/{execr}", o, isr))

    for name, o, isr in sorted(rows, key=lambda r: r[1]["pf"], reverse=True):
        tag = " <- baseline" if name == "4h/15m" else ""
        print(f"  {name:11} | {o['win']:>5} {o['pf']:>5} {o['sharpe']:>5} {o['exp']:>6} "
              f"{o['total']:>6} {o['dd']:>5} {o['n']:>5} | {isr['pf']:>5} {isr['n']:>5}{tag}")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\n({time.time()-t0:.0f}s)")
