"""Exit-MODE (red-count) permutation sweep for the Sterling Kite Engine.

Companion to ``kite_st_exit_sweep.py``. That script swept trail period/mult/
time-stop/breakeven on a single trail line. THIS one measures the new
``exit_mode`` knob — how many of the three SuperTrend lines must turn red against
the position before it exits (the counter to the 3-green entry):

    one_red          — exit when ANY one ST line is red    (= the legacy fast flip)
    two_red          — exit when any TWO lines are red      (the SHIPPED default)
    three_red        — exit when ALL THREE are red          (full reversal)
    three_red_signal — all three red AND a fresh counter-arrow (loosest)

Entry is held fixed (the triple full-alignment transition). The exit is the PURE
red-count rule — i.e. the *intended* ``exit_mode`` semantics, with the stop free to
loosen to the best still-green line. It counts reds from the SAME ``compute_regime``
trends (t_fast/t_mid/t_slow) the live ``regime.red_line_count`` uses, and gates
``three_red_signal`` on a fresh opposite ``entry_transitions`` arrow — exactly the
scanner's ``is_active`` loop. Thresholds come from ``common.exit_counter`` so this
sweep and the engine can never drift.

IMPORTANT — what this does and does NOT measure:
  * It measures whether ``two_red``/``three_red`` are WORTH anything on the data vs
    the legacy ``one_red`` (which currently has the only real IS/OOS backing —
    ``kite_st_exit_analysis.md``). The shipped ``two_red`` default is, as of this
    writing, asserted (prose in ``docs/kite_exit_counter_prod_rollout.md``), not
    measured. This script is the measurement.
  * It does NOT reproduce live behaviour. In production a monotonic fast-line
    premium ratchet (``positions.update_stop`` take-max) pins the stop and
    pre-empts the counter, so live exits ≈ ``one_red`` regardless of ``exit_mode``
    (see ``regime.best_trail_line_value`` caveat). Reconcile that ratchet first if
    these numbers say a looser mode is better.

Two lenses on REAL 7.5y 1H index candles, IS(70%)/OOS(30%):
  * delta1  — underlying pct move, 3bps friction. Isolates the exit, theta-free.
  * options — ATM CE/PE, Black-Scholes priced, full Indian F&O cost schedule.

Run (needs a logged-in Kite account in the DB; data caches to study/kite_cache):
    cd backend && python -m study.kite_st_exit_mode_sweep

Mechanics-only smoke (no Kite session; synthetic candles — NOT an edge estimate):
    cd backend && python -m study.kite_st_exit_mode_sweep --smoke

Honest note: SuperTrend-only exits on BS-modelled premium for the options lens.
Numbers require the live data pull; paper-trading on live premium is the final gate.
"""
from __future__ import annotations

import csv
import os
from typing import List, Tuple

import numpy as np

from app.engines.common.exit_counter import (
    ExitMode, exit_needs_counter_signal, get_exit_threshold,
)
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions
from app.services.kite_engine.backtest import BacktestTrade, OptionCosts, _stats_from_trades
from app.services.kite_engine.greeks import bs_price
from study import kite_data

# the four live exit modes (order = tightest → loosest)
EXIT_MODES: List[ExitMode] = ["one_red", "two_red", "three_red", "three_red_signal"]

# fixed assumptions (match kite_st_exit_sweep for cross-comparability)
IV = 0.18
DTE_DAYS = 30.0
BARS_PER_DAY = 6.0
QTY = 50
STARTING_CAPITAL = 100_000.0
OOS_FRAC = 0.30
DELTA1_COST_BPS = 3.0

BASE_CFG = SterlingKiteEngineConfig()   # entry = triple full-alignment (unchanged)


def _exit_bar(
    *, i: int, want: int, t_fast: np.ndarray, t_mid: np.ndarray, t_slow: np.ndarray,
    longs: np.ndarray, shorts: np.ndarray, threshold: int, needs_signal: bool, n: int,
) -> Tuple[int, str]:
    """First exit bar after entry ``i`` under the red-count rule. Mirrors the live
    scanner ``is_active`` loop + ``regime.red_line_count`` exactly: count lines whose
    trend is against the position; exit at the first bar with ``>= threshold`` reds
    (and, for ``*_signal`` modes, a fresh opposite entry arrow at that bar)."""
    against = -want  # long(+1) → red is -1; short(-1) → red is +1
    for j in range(i + 1, n):
        reds = ((int(t_fast[j]) == against)
                + (int(t_mid[j]) == against)
                + (int(t_slow[j]) == against))
        if reds >= threshold:
            if not needs_signal:
                return j, f"{threshold}red"
            counter = bool(shorts[j]) if want == 1 else bool(longs[j])
            if counter:
                return j, f"{threshold}red+signal"
            # threshold met but no counter-arrow yet → keep holding
    return n - 1, "series end"


def replay(*, o, h, l, c, ts, mode: ExitMode, lens: str, costs: OptionCosts) -> object:
    """Triple-alignment entries (fixed) + the red-count exit for ``mode``.
    ``lens`` is 'delta1' (underlying pct) or 'options' (ATM BS premium, full costs)."""
    o = np.asarray(o, float); h = np.asarray(h, float)
    l = np.asarray(l, float); c = np.asarray(c, float)
    n = len(c)
    trades: List[BacktestTrade] = []
    if n <= BASE_CFG.warmup + 2:
        return _stats_from_trades(trades, STARTING_CAPITAL)[0]

    r = compute_regime(o, h, l, c, BASE_CFG)
    longs, shorts = entry_transitions(r)
    threshold = get_exit_threshold(mode)
    needs_signal = exit_needs_counter_signal(mode)

    i = 0
    while i < n:
        is_long, is_short = bool(longs[i]), bool(shorts[i])
        if not (is_long or is_short):
            i += 1
            continue
        want = 1 if is_long else -1
        exit_i, reason = _exit_bar(
            i=i, want=want, t_fast=r.t_fast, t_mid=r.t_mid, t_slow=r.t_slow,
            longs=longs, shorts=shorts, threshold=threshold, needs_signal=needs_signal, n=n)
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
        for mode in EXIT_MODES:
            common = dict(mode=mode, lens=lens, costs=costs)
            sf = replay(**full, **common)
            si = replay(**is_seg, **common)
            so = replay(**oos_seg, **common)
            rows.append({
                "underlying": name, "lens": lens, "exit_mode": mode,
                "threshold": get_exit_threshold(mode),
                "trades": sf.trades, "win_rate": round(sf.win_rate * 100, 1),
                "ret_pct": sf.return_pct, "profit_factor": sf.profit_factor,
                "sharpe": sf.sharpe, "max_dd": sf.max_drawdown,
                "is_ret": si.return_pct, "is_pf": si.profit_factor,
                "oos_ret": so.return_pct, "oos_trades": so.trades, "oos_pf": so.profit_factor,
            })
    return rows


def write_csv(rows: list, path: str):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _report(rows: list, lens: str) -> None:
    print(f"\n[{lens}] mean OOS return by exit_mode "
          f"(baseline = one_red, the only IS/OOS-validated exit):")
    agg: dict = {}
    for r in rows:
        agg.setdefault(r["exit_mode"], []).append(r)
    base = float(np.mean([r["oos_ret"] for r in agg.get("one_red", [])])) if agg.get("one_red") else 0.0
    for mode in EXIT_MODES:
        rs = agg.get(mode, [])
        if not rs:
            continue
        moos = float(np.mean([r["oos_ret"] for r in rs]))
        npos = sum(1 for r in rs if r["oos_ret"] > 0)
        meanheld = float(np.mean([r["trades"] for r in rs]))
        delta = moos - base
        print(f"  {mode:<16} meanOOS={moos:+8.1f}%  ({npos}/{len(rs)} idx +)  "
              f"vs one_red {delta:+6.1f}pp   (~{meanheld:.0f} trades/idx)")


def _synthetic_data() -> dict:
    """Deterministic trending+chop synthetic candles for a MECHANICS smoke test
    only — NOT an edge estimate. Lets the full replay/run_grid path execute with no
    Kite session so the wiring (mode → threshold → exit bar → stats) is verifiable."""
    rng = np.random.default_rng(7)
    out: dict = {}
    for name, drift in (("SYN-TREND", 0.0006), ("SYN-CHOP", 0.0)):
        n = 4000
        # regime-ish: alternating up/down drifts so STs actually flip
        steps = rng.normal(drift, 0.012, n)
        flip = (np.sin(np.arange(n) / 90.0) > 0).astype(float) * 2 - 1
        c = 20000.0 * np.exp(np.cumsum(steps * flip))
        o = np.empty(n); o[0] = c[0]; o[1:] = c[:-1]
        h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.002, n)))
        l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.002, n)))
        ts = (np.arange(n, dtype=np.int64) * 3_600_000) + 1_500_000_000_000
        out[name] = {"o": o, "h": h, "l": l, "c": c, "ts": ts}
    return out


if __name__ == "__main__":
    import sys
    import warnings
    warnings.filterwarnings("ignore")

    smoke = "--smoke" in sys.argv
    if smoke:
        print("SMOKE (synthetic candles — mechanics only, NOT an edge estimate)")
        data = _synthetic_data()
    else:
        import asyncio
        data = asyncio.run(kite_data.fetch_all())

    print(f"\nExit-mode sweep: {len(EXIT_MODES)} modes × {len(data)} series × 2 lenses × 3 windows")
    all_rows: list = []
    for lens in ("delta1", "options"):
        rows = run_grid(data, lens)
        all_rows.extend(rows)
        _report(rows, lens)

    suffix = "_smoke" if smoke else ""
    out = os.path.join(os.path.dirname(__file__), f"kite_st_exit_mode_sweep_results{suffix}.csv")
    write_csv(all_rows, out)
    print(f"\n{len(all_rows)} rows -> {out}")
    if smoke:
        print("\nSmoke only proves the pipeline + mode ordering execute. For a real "
              "verdict on two_red, run WITHOUT --smoke against the live Kite pull.")
