"""Should the engine lean with the macro trend? Decide with stats.

For each armed price-action signal (symmetric detectors, pa_confirm_bars=3),
classify the 4H macro regime at signal time (EMA50 vs EMA200, with a flat band
= chop) and bucket the trade outcome (fixed SL/TP) into:
  • aligned  — long in uptrend  / short in downtrend
  • counter  — long in downtrend / short in uptrend
  • chop     — regime flat

If aligned >> counter on expectancy/PF *and it holds in both bull and bear
sub-samples*, a trend filter helps. If they're similar, neutral is fine.
"""
from __future__ import annotations

import bisect
import time
from collections import defaultdict

import numpy as np

from app.services import ohlcv_store
from app.schemas.market import Candle
from app.engines.scalping.config import default_config
from app.engines.scalping.levels import detect_levels
from app.engines.scalping.price_action import evaluate_price_action

SYMS = ["AAVE", "BTC", "ETH", "SOL", "XRP", "DOGE"]
DAYS = 540
W15, W4, MAXH = 672, 180, 96
FLAT_BAND = 0.005   # |ema50-ema200|/price below this ⇒ chop


def _load(sym, res, days):
    since = int(time.time()) - days * 86_400
    rows = ohlcv_store.get_candles(f"{sym}USD", res, limit=400_000, since=since)
    return [Candle(timestamp_ms=int(r["time"]) * 1000, open=r["open"], high=r["high"],
                   low=r["low"], close=r["close"], volume=r["volume"]) for r in rows]


def _ema(a, period):
    out = np.empty_like(a, dtype=np.float64)
    k = 2.0 / (period + 1)
    out[0] = a[0]
    for i in range(1, len(a)):
        out[i] = k * a[i] + (1 - k) * out[i - 1]
    return out


def _exit_fixed(c15, i, is_long, entry, sl, tp):
    for k in range(i + 1, min(i + 1 + MAXH, len(c15))):
        hi, lo = c15[k].high, c15[k].low
        if is_long:
            if lo <= sl: return sl, k
            if hi >= tp: return tp, k
        else:
            if hi >= sl: return sl, k
            if lo <= tp: return tp, k
    j = min(i + MAXH, len(c15) - 1)
    return c15[j].close, j


def _stats(trades):
    n = len(trades)
    if not n:
        return "n=0"
    wins = [r for r in trades if r > 0]
    gl = abs(sum(r for r in trades if r <= 0))
    pf = (sum(wins) / gl) if gl > 0 else float("inf")
    return (f"n={n:4d}  win {len(wins)/n*100:4.1f}%  PF {pf:4.2f}  "
            f"exp {np.mean(trades):+.3f}R  total {np.sum(trades):+7.1f}R")


def run():
    cfg = default_config()
    # bucket -> list of pnl_r ; also split by regime period for robustness
    buckets = defaultdict(list)          # 'aligned'/'counter'/'chop'
    by_regime = defaultdict(list)        # 'bull'/'bear'/'chop' (all signals in that regime)
    regime_bars = defaultdict(int)

    for sym in SYMS:
        c4 = _load(sym, "4h", DAYS + 60)
        c15 = _load(sym, "15m", DAYS)
        if len(c15) < W15 + 10 or len(c4) < max(W4, 220) + 5:
            print(f"  (skip {sym}: insufficient data)")
            continue
        close4 = np.array([c.close for c in c4], dtype=np.float64)
        ema50 = _ema(close4, 50)
        ema200 = _ema(close4, 200)
        ts4 = [c.timestamp_ms for c in c4]

        def regime_at(j):
            # use the last CLOSED 4h bar (j-1)
            p = j - 1
            if p < 200:
                return "chop"
            spread = (ema50[p] - ema200[p]) / max(close4[p], 1e-9)
            if spread > FLAT_BAND:  return "bull"
            if spread < -FLAT_BAND: return "bear"
            return "chop"

        cooldown, cj, levels = -1, -1, []
        i = W15
        while i < len(c15) - 1:
            j = bisect.bisect_right(ts4, c15[i].timestamp_ms)
            if j < max(W4, 201):
                i += 1; continue
            regime_bars[regime_at(j)] += 1
            if i <= cooldown:
                i += 1; continue
            if j != cj:
                cw = c4[j - W4:j]
                levels = detect_levels(np.array([c.high for c in cw]), np.array([c.low for c in cw]),
                                       np.array([c.close for c in cw]), np.array([c.timestamp_ms for c in cw], dtype=np.int64), cfg)
                cj = j
            sig = evaluate_price_action(sym, c4[j - W4:j], c15[i - W15:i + 1], levels, cfg)
            if sig.entry_ok and sig.entry and sig.stop_loss and sig.take_profit:
                is_long = sig.direction == "long"
                reg = regime_at(j)
                ex, ck = _exit_fixed(c15, i, is_long, sig.entry, sig.stop_loss, sig.take_profit)
                pnl = (1 if is_long else -1) * (ex - sig.entry) / abs(sig.entry - sig.stop_loss)
                if reg == "chop":
                    bucket = "chop"
                elif (is_long and reg == "bull") or ((not is_long) and reg == "bear"):
                    bucket = "aligned"
                else:
                    bucket = "counter"
                buckets[bucket].append(pnl)
                by_regime[reg].append(pnl)
                cooldown = ck
            i += 1

    tot = sum(regime_bars.values()) or 1
    print(f"\nRegime distribution (4H bars): "
          f"bull {regime_bars['bull']/tot*100:.0f}% · bear {regime_bars['bear']/tot*100:.0f}% · chop {regime_bars['chop']/tot*100:.0f}%")
    print(f"Window: {SYMS}, {DAYS}d\n")

    print("By trade bucket:")
    for b in ("aligned", "counter", "chop"):
        print(f"  {b:8}: {_stats(buckets[b])}")

    allt = buckets["aligned"] + buckets["counter"] + buckets["chop"]
    print("\nPolicy comparison:")
    print(f"  {'neutral (all)':22}: {_stats(allt)}")
    print(f"  {'trend-only (aligned)':22}: {_stats(buckets['aligned'])}")
    print(f"  {'drop counter-trend':22}: {_stats(buckets['aligned'] + buckets['chop'])}")

    print("\nSignals by regime period (robustness — does the edge survive in each regime?):")
    for r in ("bull", "bear", "chop"):
        print(f"  {r:5}: {_stats(by_regime[r])}")


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"\n({time.time() - t0:.0f}s)")
