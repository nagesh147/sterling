"""Extended EXIT-only permutation sweep for the Sterling Kite Engine.

The original `kite_st_sweep.py` swept the *entry-side* knobs (which of the three
fixed ST lines trails, moneyness) and proved (a) the `slow` trail is strictly
worst, (b) `early_lock` is inert, (c) long OTM/ATM options are 0/60 OOS-positive
because of theta — not the exit. This script holds the ENTRY fixed (the triple
full-alignment transition) and sweeps the EXIT/SL/TRAIL mechanics ONLY, using
SuperTrends and nothing else (no new indicators), to confirm whether anything
beats the shipped `fast`-line trail:

    trail_period   × 10 / 14 / 21              (decoupled from the entry triple)
    trail_mult     × 0.75 / 1.0 / 1.5 / 2.0    (the band width = the real lever)
    time_stop_bars × off / 48                   (cap the hold → attack theta)
    breakeven_R    × off / 1.0R                 (lift stop to entry once +1R)

Two evaluation lenses, both on REAL 7.5y 1H index candles, IS(70%)/OOS(30%):
  * delta1   — trade the underlying (pct move, 3bps friction). Isolates the EXIT
               mechanism free of theta/IV (the honest test of the exit itself).
  * options  — ATM CE/PE, Black-Scholes priced, full Indian F&O cost schedule.
               The realistic, theta-exposed lens (expect it to be far harsher).

Run (needs a logged-in Kite account in the DB; data caches to study/kite_cache):
    cd backend && python -m study.kite_st_exit_sweep

Honest note: this only sweeps SuperTrend-based exits, on BS-modelled premium for
the options lens (expired strikes have no fetchable premium). It tells you which
exit *mechanism* generalizes; paper-trading on live premium is the final gate.
"""
from __future__ import annotations

import csv
import os
from typing import List, Optional, Tuple

import numpy as np

from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions
from app.services.kite_engine.backtest import BacktestTrade, OptionCosts, _stats_from_trades
from app.services.kite_engine.greeks import bs_price
from study import kite_data

# ── exit grid (widen freely; runtime is ~linear in the product) ────────────────
TRAIL_PERIODS = [10, 14, 21]
TRAIL_MULTS = [0.75, 1.0, 1.5, 2.0]
TIME_STOPS: List[Optional[int]] = [None, 48]          # 1H bars (48 ≈ 8 trading days)
BREAKEVENS: List[Optional[float]] = [None, 1.0]       # arm a breakeven stop at +R

# fixed assumptions (match kite_st_sweep for comparability)
IV = 0.18
DTE_DAYS = 30.0
BARS_PER_DAY = 6.0
QTY = 50
STARTING_CAPITAL = 100_000.0
OOS_FRAC = 0.30
DELTA1_COST_BPS = 3.0     # round-trip friction for the underlying lens

BASE_CFG = SterlingKiteEngineConfig()   # entry = triple full-alignment (unchanged)


def _exit_bar(
    *, i: int, want: int, c: np.ndarray, trail_line: np.ndarray, trail_trend: np.ndarray,
    time_stop: Optional[int], breakeven_r: Optional[float], n: int,
) -> Tuple[int, str]:
    """First exit bar after entry ``i`` for the given SuperTrend trail + optional
    time-stop + optional breakeven-after-R. SuperTrends only — no other indicator."""
    is_long = want == 1
    entry_px = float(c[i])
    risk = abs(entry_px - float(trail_line[i])) or 1e-9
    be_armed = False
    for j in range(i + 1, n):
        cj = float(c[j])
        if breakeven_r is not None and not be_armed:
            profit = (cj - entry_px) if is_long else (entry_px - cj)
            if profit >= breakeven_r * risk:
                be_armed = True
        if be_armed and ((is_long and cj <= entry_px) or (not is_long and cj >= entry_px)):
            return j, "breakeven"
        if int(trail_trend[j]) != want:
            return j, "trail flip"
        if time_stop is not None and (j - i) >= time_stop:
            return j, "time stop"
    return n - 1, "series end"


def replay(
    *, o, h, l, c, ts, trail_period: int, trail_mult: float,
    time_stop: Optional[int], breakeven_r: Optional[float], lens: str,
    costs: OptionCosts,
) -> object:
    """Triple-alignment entries (fixed) + the swept SuperTrend exit. ``lens`` is
    'delta1' (underlying pct) or 'options' (ATM BS premium with full costs)."""
    o = np.asarray(o, float); h = np.asarray(h, float)
    l = np.asarray(l, float); c = np.asarray(c, float)
    n = len(c)
    trades: List[BacktestTrade] = []
    if n <= BASE_CFG.warmup + 2:
        return _stats_from_trades(trades, STARTING_CAPITAL)[0]

    r = compute_regime(o, h, l, c, BASE_CFG)
    longs, shorts = entry_transitions(r)
    # the trail ST runs on the SAME Heikin-Ashi candles, decoupled (period, mult)
    _, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)
    trail_line, trail_trend = compute_supertrend(ha_h, ha_l, ha_c, trail_period, trail_mult)

    i = 0
    while i < n:
        is_long, is_short = bool(longs[i]), bool(shorts[i])
        if not (is_long or is_short):
            i += 1
            continue
        want = 1 if is_long else -1
        exit_i, reason = _exit_bar(
            i=i, want=want, c=c, trail_line=trail_line, trail_trend=trail_trend,
            time_stop=time_stop, breakeven_r=breakeven_r, n=n)
        held = exit_i - i
        if lens == "delta1":
            entry_px, exit_px = float(c[i]), float(c[exit_i])
            move = (exit_px - entry_px) / entry_px if is_long else (entry_px - exit_px) / entry_px
            net = move - DELTA1_COST_BPS / 1e4
            trades.append(BacktestTrade(
                entry_ms=int(ts[i]), exit_ms=int(ts[exit_i]),
                direction="long" if is_long else "short",
                entry_premium=round(entry_px, 2), exit_premium=round(exit_px, 2), qty=1,
                gross_pnl=round(move * 1e5, 2), costs=round(DELTA1_COST_BPS / 1e4 * 1e5, 2),
                net_pnl=round(net * 1e5, 2), bars_held=held, exit_reason=reason))
        else:  # options
            opt_type = "CE" if is_long else "PE"
            spot0 = float(c[i])
            strike = round(spot0, 0)  # ATM
            exit_dte = max(0.0, DTE_DAYS - held / max(BARS_PER_DAY, 1e-9))
            entry_px = bs_price(spot=spot0, strike=strike, dte_days=DTE_DAYS, iv=IV, option_type=opt_type)
            exit_px = bs_price(spot=float(c[exit_i]), strike=strike, dte_days=exit_dte, iv=IV, option_type=opt_type)
            gross = (exit_px - entry_px) * QTY
            ch = costs.round_trip(entry_px, exit_px, QTY)
            trades.append(BacktestTrade(
                entry_ms=int(ts[i]), exit_ms=int(ts[exit_i]),
                direction="long-call" if is_long else "long-put",
                entry_premium=round(entry_px, 2), exit_premium=round(exit_px, 2), qty=QTY,
                gross_pnl=round(gross, 2), costs=round(ch, 2), net_pnl=round(gross - ch, 2),
                bars_held=held, exit_reason=reason))
        i = exit_i + 1

    return _stats_from_trades(trades, STARTING_CAPITAL)[0]


def _slice(arrs, lo, hi):
    return {k: arrs[k][lo:hi] for k in ("o", "h", "l", "c", "ts")}


def run_grid(data: dict, lens: str) -> list:
    costs = OptionCosts()
    rows: list = []
    for name, arrs in data.items():
        n = len(arrs["c"])
        oos_lo = int(n * (1 - OOS_FRAC))
        full = {k: arrs[k] for k in ("o", "h", "l", "c", "ts")}
        is_seg, oos_seg = _slice(arrs, 0, oos_lo), _slice(arrs, oos_lo, n)
        for p in TRAIL_PERIODS:
            for m in TRAIL_MULTS:
                for tstop in TIME_STOPS:
                    for ber in BREAKEVENS:
                        common = dict(trail_period=p, trail_mult=m, time_stop=tstop,
                                      breakeven_r=ber, lens=lens, costs=costs)
                        sf = replay(**full, **common)
                        si = replay(**is_seg, **common)
                        so = replay(**oos_seg, **common)
                        rows.append({
                            "underlying": name, "lens": lens, "trail_period": p, "trail_mult": m,
                            "time_stop": tstop if tstop is not None else "off",
                            "breakeven_r": ber if ber is not None else "off",
                            "trades": sf.trades, "win_rate": round(sf.win_rate * 100, 1),
                            "ret_pct": sf.return_pct, "profit_factor": sf.profit_factor,
                            "sharpe": sf.sharpe, "max_dd": sf.max_drawdown,
                            "is_ret": si.return_pct, "is_pf": si.profit_factor,
                            "oos_ret": so.return_pct, "oos_trades": so.trades, "oos_pf": so.profit_factor,
                        })
    return rows


def is_oos_spearman(rows: list) -> float:
    """Rank corr of IS vs OOS return across configs — robustness proxy (>0 = signal)."""
    items = rows
    if len(items) < 3:
        return 0.0
    def rank(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        rk = [0] * len(vals)
        for pos, idx in enumerate(order):
            rk[idx] = pos
        return rk
    ri, ro = rank([r["is_ret"] for r in items]), rank([r["oos_ret"] for r in items])
    nn = len(items)
    d2 = sum((ri[i] - ro[i]) ** 2 for i in range(nn))
    return round(1 - 6 * d2 / (nn * (nn * nn - 1)), 3)


def write_csv(rows: list, path: str):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    import asyncio
    import warnings
    warnings.filterwarnings("ignore")
    data = asyncio.run(kite_data.fetch_all())
    n_cfg = len(TRAIL_PERIODS) * len(TRAIL_MULTS) * len(TIME_STOPS) * len(BREAKEVENS)
    print(f"\nExit sweep: {n_cfg} exit configs × {len(data)} indices × 2 lenses × 3 windows")
    all_rows: list = []
    for lens in ("delta1", "options"):
        rows = run_grid(data, lens)
        all_rows.extend(rows)
        corr = is_oos_spearman(rows)
        print(f"\n[{lens}] IS->OOS Spearman (robustness): {corr}")
        # current shipped exit ≈ trail_period 21, mult 1.0 ("fast"), no time-stop/breakeven
        base = [r for r in rows if r["trail_period"] == 21 and r["trail_mult"] == 1.0
                and r["time_stop"] == "off" and r["breakeven_r"] == "off"]
        if base:
            b = max(base, key=lambda r: r["oos_ret"])
            print(f"  shipped-exit baseline (p21,m1.0): mean OOS "
                  f"{np.mean([r['oos_ret'] for r in base]):+.1f}%")
        print(f"  top 8 by mean-OOS across indices:")
        agg: dict = {}
        for r in rows:
            key = (r["trail_period"], r["trail_mult"], r["time_stop"], r["breakeven_r"])
            agg.setdefault(key, []).append(r["oos_ret"])
        top = sorted(agg.items(), key=lambda kv: np.mean(kv[1]), reverse=True)[:8]
        for (p, m, tstop, ber), v in top:
            print(f"    p={p:<3} m={m:<4} tstop={str(tstop):<3} be={str(ber):<3} "
                  f"meanOOS={np.mean(v):+8.1f}%  ({sum(1 for x in v if x>0)}/{len(v)} idx +)")
    out = os.path.join(os.path.dirname(__file__), "kite_st_exit_sweep_results.csv")
    write_csv(all_rows, out)
    print(f"\n{len(all_rows)} rows -> {out}")
