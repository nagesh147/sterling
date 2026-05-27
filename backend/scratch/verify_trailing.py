"""A/B the trailing-stop change on real data.

Detects armed price-action signals (pa_confirm_bars=3) over real 4H+15m data,
then exits each one three ways and compares:
  • fixed     — original SL/TP, no trailing
  • old_trail — TrailingStopEngine with initial_risk=0 (legacy breakeven-only)
  • new_trail — TrailingStopEngine with initial_risk set (progressive + R step-locks)

Trailing runs bar-by-bar exactly as the live monitor does (scalping PERCENTAGE
trail), so this isolates the engine change.
"""
from __future__ import annotations

import bisect
import time
from collections import Counter

import numpy as np

from app.services import ohlcv_store
from app.schemas.market import Candle
from app.core.trading_mode import MODES
from app.engines.scalping.config import default_config
from app.engines.scalping.levels import detect_levels
from app.engines.scalping.price_action import evaluate_price_action
from app.engines.directional.trailing_stop import TrailState, TrailingStopEngine

SYMS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "AVAX", "LINK", "LTC"]
DAYS = 90
W15, W4, MAXH = 672, 180, 96
SCALP = MODES["scalping"]              # PERCENTAGE trail, trail_pct=0.5
ENG = TrailingStopEngine()


def _load(sym, res, days):
    since = int(time.time()) - days * 86_400
    rows = ohlcv_store.get_candles(f"{sym}USD", res, limit=300_000, since=since)
    return [Candle(timestamp_ms=int(r["time"]) * 1000, open=r["open"], high=r["high"],
                   low=r["low"], close=r["close"], volume=r["volume"]) for r in rows]


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


def _exit_trail(c15, i, is_long, entry, sl, tp, risk, use_R):
    """Walk the trail bar-by-bar; exit on trail stop or TP touch."""
    st = TrailState(mode=SCALP.trail_mode, current_stop=sl, highest_seen=entry,
                    lowest_seen=entry, trail_mult=SCALP.trail_atr_mult,
                    initial_risk=(risk if use_R else 0.0))
    direction = "long" if is_long else "short"
    for k in range(i + 1, min(i + 1 + MAXH, len(c15))):
        win = c15[max(0, k - 30):k + 1]
        tu = ENG.update(state=st, candles=win, st_value=0.0, direction=direction,
                        entry_price=entry, mode=SCALP, initial_tp=tp)
        hi, lo = c15[k].high, c15[k].low
        # TP touch first within the bar would be optimistic; check stop first (pessimistic).
        if tu.stopped_out:
            return st.current_stop, k
        if is_long and hi >= tp:
            return tp, k
        if (not is_long) and lo <= tp:
            return tp, k
    j = min(i + MAXH, len(c15) - 1)
    return c15[j].close, j


def _metrics(name, trades, holds):
    n = len(trades)
    if not n:
        print(f"  {name}: no trades"); return
    wins = [r for r in trades if r > 0]
    gl = abs(sum(r for r in trades if r <= 0))
    eq = np.cumsum(trades); dd = float(np.max(np.maximum.accumulate(eq) - eq))
    pf = (sum(wins) / gl) if gl > 0 else float("inf")
    print(f"  {name:10}: win {len(wins)/n*100:4.1f}%  PF {pf:4.2f}  "
          f"exp {np.mean(trades):+.3f}R  total {np.sum(trades):+6.1f}R  "
          f"maxDD {dd:4.1f}R  avgHold {np.mean(holds):4.1f} bars")


def run():
    cfg = default_config()  # pa_confirm_bars=3
    sigs = []
    for sym in SYMS:
        c4 = _load(sym, "4h", DAYS + 40); c15 = _load(sym, "15m", DAYS)
        if len(c15) < W15 + 10 or len(c4) < W4 + 5:
            continue
        ts4 = [c.timestamp_ms for c in c4]
        cooldown, cj, levels = -1, -1, []
        i = W15
        while i < len(c15) - 1:
            if i <= cooldown:
                i += 1; continue
            j = bisect.bisect_right(ts4, c15[i].timestamp_ms)
            if j < W4:
                i += 1; continue
            if j != cj:
                cw = c4[j - W4:j]
                levels = detect_levels(np.array([c.high for c in cw]), np.array([c.low for c in cw]),
                                       np.array([c.close for c in cw]), np.array([c.timestamp_ms for c in cw], dtype=np.int64), cfg)
                cj = j
            sig = evaluate_price_action(sym, c4[j - W4:j], c15[i - W15:i + 1], levels, cfg)
            if sig.entry_ok and sig.entry and sig.stop_loss and sig.take_profit:
                sigs.append((c15, i, sig.direction == "long", sig.entry, sig.stop_loss, sig.take_profit))
                # block re-entry ~ until fixed-exit resolves
                _, ce = _exit_fixed(c15, i, sig.direction == "long", sig.entry, sig.stop_loss, sig.take_profit)
                cooldown = ce
            i += 1

    print(f"Armed signals: {len(sigs)}  ({SYMS}, {DAYS}d)\n")
    for policy in ("fixed", "old_trail", "new_trail"):
        trades, holds = [], []
        for (c15, i, is_long, entry, sl, tp) in sigs:
            risk = abs(entry - sl)
            if policy == "fixed":
                ex, ck = _exit_fixed(c15, i, is_long, entry, sl, tp)
            else:
                ex, ck = _exit_trail(c15, i, is_long, entry, sl, tp, risk, use_R=(policy == "new_trail"))
            dirmult = 1 if is_long else -1
            trades.append(dirmult * (ex - entry) / risk if risk > 0 else 0.0)
            holds.append(ck - i)
        _metrics(policy, trades, holds)


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"\n({time.time() - t0:.0f}s)")
