"""Replay the Kite Sterling Kite Engine on REAL 1H index/stock data (Yahoo).

No Kite login needed — pulls real 1H bars from Yahoo Finance (same source as
``equity_pipeline``) for the index underlyings + a few liquid F&O stocks, then
runs the engine bar-by-bar exactly as the live scanner + trailing lifecycle
would (enter on a fresh full-alignment transition; ratchet + exit on the trail
SuperTrend flip). Reports trades, win-rate, recent signals and the current
"ready" state, with an emphasis on the last 7 days.

CAVEATS (honest):
  * Outcomes are the UNDERLYING directional move (entry close → exit close), NOT
    option-premium P&L — options add convexity/decay we have no history for here.
  * Yahoo 1H sessions differ slightly from Kite's; this validates the engine's
    setup detection + trailing logic on real Indian-market structure, not fills.

Run:  cd backend && PYTHONWARNINGS=ignore python3 -m study.kite_sterling_kite_engine_replay
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np

from app.domain.models import Candle
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions
from study.equity_pipeline import fetch_chart, yahoo_to_frame

_IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# Yahoo 1H universe: the four index underlyings + a few liquid F&O stocks.
UNIVERSE = [
    ("NIFTY 50", "^NSEI"),
    ("NIFTY BANK", "^NSEBANK"),
    ("NIFTY FIN SERVICE", "NIFTY_FIN_SERVICE.NS"),
    ("SENSEX", "^BSESN"),
    ("RELIANCE", "RELIANCE.NS"),
    ("HDFCBANK", "HDFCBANK.NS"),
    ("INFY", "INFY.NS"),
    ("TCS", "TCS.NS"),
]


@dataclass
class Trade:
    i0: int
    i1: int
    direction: str
    entry: float
    exit: float
    init_stop: float
    t0: int
    t1: int
    reason: str

    @property
    def pnl(self) -> float:
        return (self.exit - self.entry) if self.direction == "long" else (self.entry - self.exit)

    @property
    def r_mult(self) -> float:
        risk = abs(self.entry - self.init_stop) or 1e-9
        return self.pnl / risk

    @property
    def pct(self) -> float:
        return 100.0 * self.pnl / (self.entry or 1.0)


def _candles(df) -> List[Candle]:
    return [Candle(timestamp_ms=int(t) * 1000, open=float(o), high=float(h),
                   low=float(l), close=float(c), volume=float(v))
            for t, o, h, l, c, v in df[["time", "open", "high", "low", "close", "volume"]].itertuples(index=False)]


def _ist(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, _IST).strftime("%Y-%m-%d %H:%M")


def replay(candles: Sequence[Candle], cfg: SterlingKiteEngineConfig):
    """Faithful live-loop replay using the engine's causal regime arrays."""
    o = np.array([c.open for c in candles], float)
    h = np.array([c.high for c in candles], float)
    l = np.array([c.low for c in candles], float)
    c = np.array([c.close for c in candles], float)
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    t_trail = r.trend(cfg.trail_target)
    l_trail = r.line(cfg.trail_target)
    t_slow = r.trend("slow")

    trades: List[Trade] = []
    pos: Optional[dict] = None
    for i in range(cfg.warmup + 1, len(candles)):
        if pos is None:
            if longs[i] or shorts[i]:
                d = "long" if longs[i] else "short"
                pos = {"i0": i, "entry": float(c[i]), "dir": d, "stop": float(l_trail[i]),
                       "init": float(l_trail[i]), "t0": candles[i].timestamp_ms}
            continue
        # manage open position
        if pos["dir"] == "long":
            pos["stop"] = max(pos["stop"], float(l_trail[i]))
            flip = t_trail[i] == -1
        else:
            pos["stop"] = min(pos["stop"], float(l_trail[i]))
            flip = t_trail[i] == 1
        reason = "red_line_exit"
        if not flip and cfg.early_lock:
            risk = abs(pos["entry"] - pos["init"]) or 1e-9
            profit = (c[i] - pos["entry"]) if pos["dir"] == "long" else (pos["entry"] - c[i])
            if profit >= cfg.early_lock_profit_r * risk:
                flip = (t_slow[i] == -1) if pos["dir"] == "long" else (t_slow[i] == 1)
                reason = "early_lock_slow_flip"
        if flip:
            trades.append(Trade(pos["i0"], i, pos["dir"], pos["entry"], float(c[i]),
                                pos["init"], pos["t0"], candles[i].timestamp_ms, reason))
            pos = None
    return trades, r, (longs, shorts), pos


def _report(name: str, candles: List[Candle], cfg: SterlingKiteEngineConfig, week_cutoff_ms: int):
    trades, r, (longs, shorts), pos = replay(candles, cfg)
    n = len(candles)
    last = n - 1
    align = f"f{int(r.t_fast[last]):+d} m{int(r.t_mid[last]):+d} s{int(r.t_slow[last]):+d}"
    regime = "BULL" if r.bull[last] else "BEAR" if r.bear[last] else "FLAT"
    ready = bool(longs[last] or shorts[last])

    closed = trades
    wins = [t for t in closed if t.pnl > 0]
    wr = 100.0 * len(wins) / len(closed) if closed else 0.0
    avg_r = float(np.mean([t.r_mult for t in closed])) if closed else 0.0
    sum_r = float(np.sum([t.r_mult for t in closed])) if closed else 0.0
    avg_hold = float(np.mean([t.i1 - t.i0 for t in closed])) if closed else 0.0

    recent_entries = [i for i in range(cfg.warmup + 1, n)
                      if (longs[i] or shorts[i]) and candles[i].timestamp_ms >= week_cutoff_ms]

    print(f"\n══ {name} ══  ({n} 1H bars · {_ist(candles[0].timestamp_ms)} → {_ist(candles[last].timestamp_ms)})")
    print(f"   trades={len(closed)}  win%={wr:5.1f}  avgR={avg_r:+.2f}  sumR={sum_r:+.1f}  avgHold={avg_hold:.0f} bars")
    print(f"   NOW: regime={regime}  align[{align}]  {'>>> READY (fresh signal on last bar)' if ready else ''}")
    if pos is not None:
        upnl = (candles[last].close - pos['entry']) if pos['dir'] == 'long' else (pos['entry'] - candles[last].close)
        print(f"   OPEN: {pos['dir'].upper()} since {_ist(pos['t0'])} @ {pos['entry']:.1f}  "
              f"trail-stop {pos['stop']:.1f}  uPnL {upnl:+.1f} ({100*upnl/pos['entry']:+.2f}%)")
    if recent_entries:
        print(f"   ── entries in last 7 days ({len(recent_entries)}):")
        for i in recent_entries:
            d = "LONG/CE" if longs[i] else "SHORT/PE"
            print(f"      {_ist(candles[i].timestamp_ms)}  {d:8s}  entry {candles[i].close:9.1f}  stop {float(r.line(cfg.trail_target)[i]):9.1f}")
    else:
        print("   ── no fresh entries in the last 7 days")
    return closed


def main():
    cfg = SterlingKiteEngineConfig()
    print(f"Kite Sterling Kite Engine — REAL 1H replay  (trail={cfg.trail_target}, warmup={cfg.warmup})")
    all_trades: List[Trade] = []
    now_ms = int(dt.datetime.now(tz=dt.timezone.utc).timestamp() * 1000)
    week_cutoff = now_ms - 7 * 86_400_000
    for name, ysym in UNIVERSE:
        try:
            df = yahoo_to_frame(fetch_chart(ysym, years=1, interval="60m"))
        except Exception as exc:  # noqa: BLE001
            print(f"\n══ {name} ══  fetch failed: {exc}")
            continue
        if len(df) <= cfg.warmup + 2:
            print(f"\n══ {name} ══  insufficient data ({len(df)} bars)")
            continue
        all_trades += _report(name, _candles(df), cfg, week_cutoff)

    if all_trades:
        wins = [t for t in all_trades if t.pnl > 0]
        print("\n" + "═" * 60)
        print(f"AGGREGATE  trades={len(all_trades)}  win%={100*len(wins)/len(all_trades):.1f}  "
              f"avgR={np.mean([t.r_mult for t in all_trades]):+.2f}  "
              f"sumR={np.sum([t.r_mult for t in all_trades]):+.1f}")
        print("CAVEAT: underlying directional P&L (not option premium); Yahoo 1H ≈ Kite 1H, not identical.")


if __name__ == "__main__":
    main()
