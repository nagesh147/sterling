"""Real-data verification of the price-action confirmation-window change.

Walks real stored 4H + 15m candles bar-by-bar, runs the ACTUAL
`evaluate_price_action` engine at each step (no lookahead in signal gen), and
simulates every armed signal forward to SL/TP. Compares pa_confirm_bars = 1
(old current-bar-only) vs 3 (new default) vs 5.
"""
from __future__ import annotations

import bisect
import time
from collections import Counter

import numpy as np

from app.services import ohlcv_store
from app.schemas.market import Candle
from app.engines.sterling_engine.config import default_config
from app.engines.sterling_engine.levels import detect_levels
from app.engines.sterling_engine.price_action import evaluate_price_action

SYMS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "AVAX", "LINK", "LTC"]
DAYS = 90
W15 = 672   # trailing 15m bars handed to the evaluator (mirrors production load)
W4 = 180    # trailing 4h bars for level detection
MAXH = 96   # max hold = 1 day of 15m bars


def _load(sym: str, res: str, days: int):
    since = int(time.time()) - days * 86_400
    rows = ohlcv_store.get_candles(f"{sym}USD", res, limit=300_000, since=since)
    return [
        Candle(timestamp_ms=int(r["time"]) * 1000, open=r["open"], high=r["high"],
               low=r["low"], close=r["close"], volume=r["volume"])
        for r in rows
    ]


def _metrics(trades: list[float]) -> dict:
    n = len(trades)
    if n == 0:
        return {"trades": 0}
    wins = [r for r in trades if r > 0]
    losses = [r for r in trades if r <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    # R-equity curve max drawdown
    eq = np.cumsum(trades)
    peak = np.maximum.accumulate(eq)
    dd = float(np.max(peak - eq)) if n else 0.0
    return {
        "trades": n,
        "win_rate": round(len(wins) / n * 100, 1),
        "avg_R": round(float(np.mean(trades)), 3),
        "median_R": round(float(np.median(trades)), 3),
        "expectancy_R": round(float(np.mean(trades)), 3),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf"),
        "total_R": round(float(np.sum(trades)), 1),
        "max_dd_R": round(dd, 1),
        "best_R": round(max(trades), 2),
        "worst_R": round(min(trades), 2),
    }


def run(confirm_bars: int) -> dict:
    cfg = default_config().model_copy(update={"pa_confirm_bars": confirm_bars})
    armed = 0
    near_miss = 0          # pattern found but risk plan rejected
    longs = 0
    shorts = 0
    patterns: Counter = Counter()
    trades: list[float] = []
    bars_scanned = 0

    for sym in SYMS:
        c4 = _load(sym, "4h", DAYS + 40)
        c15 = _load(sym, "15m", DAYS)
        if len(c15) < W15 + 10 or len(c4) < W4 + 5:
            continue
        ts4 = [c.timestamp_ms for c in c4]

        cooldown_until = -1            # one trade at a time per symbol (mirrors idempotency guard)
        cached_j = -1
        levels = []
        i = W15
        while i < len(c15):
            bars_scanned += 1
            if i <= cooldown_until:
                i += 1
                continue
            ts = c15[i].timestamp_ms
            j = bisect.bisect_right(ts4, ts)
            if j < W4:
                i += 1
                continue
            # recompute 4h levels only when a new 4h bar has closed
            if j != cached_j:
                c4win = c4[j - W4:j]
                h4 = np.array([c.high for c in c4win]); l4 = np.array([c.low for c in c4win])
                cl4 = np.array([c.close for c in c4win]); t4 = np.array([c.timestamp_ms for c in c4win], dtype=np.int64)
                levels = detect_levels(h4, l4, cl4, t4, cfg)
                cached_j = j
            else:
                c4win = c4[j - W4:j]

            c15win = c15[i - W15:i + 1]
            sig = evaluate_price_action(sym, c4win, c15win, levels, cfg)

            if sig.direction in ("long", "short") and not sig.entry_ok:
                near_miss += 1

            if sig.entry_ok and sig.entry and sig.stop_loss and sig.take_profit:
                armed += 1
                patterns[sig.pattern] += 1
                is_long = sig.direction == "long"
                longs += int(is_long); shorts += int(not is_long)

                entry, sl, tp = sig.entry, sig.stop_loss, sig.take_profit
                risk = abs(entry - sl)
                exitp = None
                close_idx = min(i + MAXH, len(c15) - 1)
                for k in range(i + 1, min(i + 1 + MAXH, len(c15))):
                    hi, lo = c15[k].high, c15[k].low
                    if is_long:
                        if lo <= sl:   exitp, close_idx = sl, k; break   # SL checked first (pessimistic)
                        if hi >= tp:   exitp, close_idx = tp, k; break
                    else:
                        if hi >= sl:   exitp, close_idx = sl, k; break
                        if lo <= tp:   exitp, close_idx = tp, k; break
                if exitp is None:
                    exitp = c15[close_idx].close
                dirmult = 1 if is_long else -1
                pnl_r = dirmult * (exitp - entry) / risk if risk > 0 else 0.0
                trades.append(round(pnl_r, 4))
                cooldown_until = close_idx     # block re-entry until this trade resolves
            i += 1

    return {
        "confirm_bars": confirm_bars,
        "bars_scanned": bars_scanned,
        "armed": armed,
        "near_miss": near_miss,
        "long": longs, "short": shorts,
        "patterns": dict(patterns.most_common()),
        **_metrics(trades),
    }


if __name__ == "__main__":
    print(f"Universe: {SYMS}")
    print(f"Window: last {DAYS} days · 15m execution / 4h structure · max hold {MAXH} bars (1d)\n")
    for cb in (1, 3, 5):
        t0 = time.time()
        r = run(cb)
        r["_secs"] = round(time.time() - t0, 1)
        print(f"=== pa_confirm_bars = {cb} ===")
        for k, v in r.items():
            if k == "patterns":
                print(f"  patterns      : {v}")
            else:
                print(f"  {k:14}: {v}")
        print()
