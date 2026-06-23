"""Phase-0b: Delta-1 (futures-equivalent) baseline — the honest floor.

Replays the Sterling Kite Engine signal entries/exits on the UNDERLYING directly
(no option wrapper). This establishes the "best-case" directional edge of the
signal itself, free of theta/IV/slippage from the options wrapper.

The sweep paper (kite_st_permutation_backtest.md) already showed delta-1 is
OOS-positive on all 4 indices. This script produces comparable stats so we can
benchmark Deep-ITM and options vehicles against the theoretical delta-1 ceiling.

Costs: futures brokerage ₹20/order + STT ₹0.0125% + GST + exchange charges.

Run:  python -m study.kite_st_futures
"""
from __future__ import annotations

import asyncio
import csv
import os
import warnings
from dataclasses import dataclass

import numpy as np

from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions
from study import kite_data

TRAIL_TARGET = "mid"
OOS_FRAC = 0.30
QTY = 50          # lot-equivalent for notional sizing
STARTING_CAPITAL = 500_000.0
BARS_PER_DAY = 6.0

# Indian futures cost schedule (approximate)
BROKERAGE = 20.0                # per order (flat)
STT_SELL = 0.0125 / 100         # STT on sell-side turnover
EXCHANGE_FEES = 0.0019 / 100    # NSE exchange charges
GST_RATE = 0.18                 # on brokerage + exchange


@dataclass
class FuturesTrade:
    entry_ms: int; exit_ms: int; direction: str
    entry_price: float; exit_price: float; qty: int
    gross_pnl: float; costs: float; net_pnl: float
    bars_held: int; exit_reason: str


def _costs(entry: float, exit_price: float, qty: int) -> float:
    """Round-trip costs for one futures trade."""
    turnover = (entry + exit_price) * qty
    brok = BROKERAGE * 2  # entry + exit
    stt = exit_price * qty * STT_SELL
    exch = turnover * EXCHANGE_FEES
    gst = (brok + exch) * GST_RATE
    return brok + stt + exch + gst


def replay_futures(*, o, h, l, c, ts, cfg, trail_target, qty, starting_capital):
    """Delta-1 replay on the underlying. No option wrapper."""
    n = len(c)
    trades: list = []
    if n <= cfg.warmup + 2:
        return trades

    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    trend = r.trend(trail_target)
    slow = r.trend("slow")
    line = r.line(trail_target)

    i = 0
    while i < n:
        is_long, is_short = bool(longs[i]), bool(shorts[i])
        if not (is_long or is_short):
            i += 1
            continue
        want = 1 if is_long else -1
        sign = 1.0 if is_long else -1.0
        entry = float(c[i])

        exit_i, reason = n - 1, "series end"
        for j in range(i + 1, n):
            if int(trend[j]) != want:
                exit_i, reason = j, "trail flip"
                break

        exit_px = float(c[exit_i])
        gross = (exit_px - entry) * sign * qty
        cost = _costs(entry, exit_px, qty)
        trades.append(FuturesTrade(
            entry_ms=int(ts[i]), exit_ms=int(ts[exit_i]),
            direction="long" if is_long else "short",
            entry_price=entry, exit_price=exit_px, qty=qty,
            gross_pnl=round(gross, 2), costs=round(cost, 2),
            net_pnl=round(gross - cost, 2),
            bars_held=exit_i - i, exit_reason=reason))
        i = exit_i + 1

    return trades


def _stats(trades, capital):
    if not trades:
        return {}
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    gross = sum(t.gross_pnl for t in trades)
    costs = sum(t.costs for t in trades)
    net = sum(t.net_pnl for t in trades)
    gross_win = sum(t.net_pnl for t in wins) if wins else 0
    gross_loss = abs(sum(t.net_pnl for t in losses)) if losses else 1e-9
    return {
        "trades": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "net_pnl": round(net, 0),
        "ret_pct": round(net / capital * 100, 1),
        "pf": round(gross_win / gross_loss, 2) if gross_loss else 0,
        "avg_hold": round(np.mean([t.bars_held for t in trades]) / BARS_PER_DAY, 1),
        "costs": round(costs, 0),
    }


def run_futures_baseline(data: dict) -> list:
    rows = []
    cfg = SterlingKiteEngineConfig(trail_target=TRAIL_TARGET)
    for name, arrs in data.items():
        n = len(arrs["c"])
        oos_lo = int(n * (1 - OOS_FRAC))
        full = {k: arrs[k] for k in ("o", "h", "l", "c", "ts")}
        oos_seg = {k: arrs[k][oos_lo:n] for k in ("o", "h", "l", "c", "ts")}

        tf = replay_futures(**full, cfg=cfg, trail_target=TRAIL_TARGET,
                            qty=QTY, starting_capital=STARTING_CAPITAL)
        to = replay_futures(**oos_seg, cfg=cfg, trail_target=TRAIL_TARGET,
                            qty=QTY, starting_capital=STARTING_CAPITAL)
        sf = _stats(tf, STARTING_CAPITAL)
        so = _stats(to, STARTING_CAPITAL)
        rows.append({
            "underlying": name,
            **{f"full_{k}": v for k, v in sf.items()},
            **{f"oos_{k}": v for k, v in so.items()},
        })
    return rows


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    data = asyncio.run(kite_data.fetch_all())
    print(f"Delta-1 (futures) baseline: {len(data)} indices")
    rows = run_futures_baseline(data)
    out = os.path.join(os.path.dirname(__file__), "kite_st_futures_results.csv")
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"{len(rows)} rows → {out}")
    for r in rows:
        print(f"  {r['underlying']:<18} "
              f"full: {r.get('full_ret_pct', r.get('full_ret_pct', '?'))}% PF={r.get('full_pf', '?')}  "
              f"OOS: {r.get('oos_ret_pct', r.get('oos_ret_pct', '?'))}% PF={r.get('oos_pf', '?')}")
