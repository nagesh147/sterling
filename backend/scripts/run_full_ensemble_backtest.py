#!/usr/bin/env python3
"""
Sterling v4 — Full Real-Data Ensemble Comparison (Fast Version)
==============================================================
Optimized for throughput:
- Regime skipped (use "neutral" — regime mostly neutral anyway)
- Aggressive sampling: 5m→8x, 15m→4x, 30m→2x, 1h→1x, 4h→1x
- Lookback 80 bars instead of 150
- Single worker (GIL contention makes threading poor)
- Pre-build track objects once
"""
from __future__ import annotations
import os, sys, json, sqlite3, time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np

from app.schemas.market import Candle
from app.engines.directional.tracks.base import NEUTRAL_TRACK_SIGNAL
from app.engines.directional.tracks.trend_following import TrendFollowingTrack
from app.engines.directional.tracks.vcp_track import VCPTrack, VCPTrackConfig
from app.engines.directional.tracks.fade_extremes import FadeExtremesTrack
from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS

DB_PATH = Path(__file__).resolve().parent.parent / "sterling_paper.db"
SAMPLE = {"5m": 8, "15m": 4, "30m": 2, "1h": 1, "4h": 1}
MAX_BARS = 25000
REGIME_EVERY = 30


def load_candles(symbol, resolution, sample_every=1, max_bars=MAX_BARS):
    uri = f"file:{DB_PATH}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, timeout=60.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    db_res = resolution.lower()
    rows = cur.execute(
        'SELECT * FROM ohlcv WHERE symbol=? AND resolution=? ORDER BY time ASC',
        (symbol.upper(), db_res)
    ).fetchall()
    conn.close()
    candles = [Candle(
        timestamp_ms=r["time"] * 1000,
        open=float(r["open"]), high=float(r["high"]),
        low=float(r["low"]), close=float(r["close"]),
        volume=float(r["volume"]),
    ) for r in rows]
    if len(candles) > max_bars:
        candles = candles[::sample_every]
    return candles


def precompute(candles, regime_every=REGIME_EVERY):
    n = len(candles)
    op = np.array([c.open  for c in candles], dtype=np.float64)
    hi = np.array([c.high  for c in candles], dtype=np.float64)
    lo = np.array([c.low   for c in candles], dtype=np.float64)
    cl = np.array([c.close for c in candles], dtype=np.float64)

    tr = np.empty(n, dtype=np.float64)
    tr[0] = hi[0] - lo[0]
    tr[1:] = np.maximum(hi[1:] - lo[1:], np.abs(hi[1:] - cl[:-1]))
    tr[1:] = np.maximum(tr[1:], np.abs(lo[1:] - cl[:-1]))
    atrs = np.zeros(n, dtype=np.float64)
    atrs[14] = float(np.mean(tr[1:15]))
    for i in range(15, n):
        atrs[i] = (atrs[i-1] * 13 + tr[i]) / 14

    # Regime labels — forward-filled at coarse interval
    r_labels = ["neutral"] * n
    from app.engines.directional.regime_engine import compute_regime
    for bar_i in range(0, n, regime_every):
        lookback = candles[max(0, bar_i - 80):bar_i]
        if len(lookback) < 30:
            continue
        try:
            r_obj = compute_regime(
                lookback[-120:] if len(lookback) >= 120 else lookback,
                macro_filter="adx_4h"
            )
            label = r_obj.macro_regime.value.lower() if r_obj else "neutral"
        except:
            label = "neutral"
        for j in range(bar_i, min(bar_i + regime_every, n)):
            r_labels[j] = label

    return dict(op=op, hi=hi, lo=lo, cl=cl, atrs=atrs,
                r_labels=r_labels, n=n)


@dataclass
class BMetrics:
    label: str
    trade_count: int; win_rate: float; sharpe: float
    profit_factor: float; max_drawdown: float; cagr: float
    avg_score: float; avg_edge: float


def run_backtest(pc, candles, use_new, entry_thresh=7.0):
    _TRACK_WINDOWS.clear()
    n = pc["n"]
    if n < 60:
        return None

    cfg_stop = 2.0; cfg_tp1 = 1.5; cfg_trail = 3.0; cfg_hold = 30

    tf_t = TrendFollowingTrack()
    vc_t = VCPTrack(VCPTrackConfig(profile_key="btc_scalping_15m"))
    mr_t = FadeExtremesTrack()
    track_map = {"trend_following": tf_t, "vcp": vc_t, "mean_reversion": mr_t}

    equity = [1.0]; eq_val = 1.0
    pos = None; trades = []
    scores_list = []; edges_list = []

    for bar_i in range(30, n):
        lookback = candles[max(0, bar_i - 80):bar_i]
        if len(lookback) < 30:
            continue

        r_label = pc["r_labels"][bar_i]

        cands = []
        for nm in ["trend_following", "vcp", "mean_reversion"]:
            try:
                cands.append(track_map[nm].compute(lookback, None))
            except:
                cands.append(NEUTRAL_TRACK_SIGNAL)

        sig = compute_ensemble_signal(cands, regime_label=r_label)

        if use_new:
            direction = sig.direction
            score = sig.ensemble_score
            strength = sig.strength
            avg_edge = sig.edge_per_trade
        else:
            active_states = [st for st in sig.tracks if st.trend_dir != 0]
            total_w = sum(st.weight for st in active_states)
            n_active = len(active_states)
            old_dir = int(np.sign(
                sum(st.weight * st.trend_dir for st in active_states))) \
                if (total_w > 0 and n_active > 0) else 0
            old_score = (total_w / n_active * 20.0) if n_active > 0 else 0.0
            max_s = max((st.raw_score for st in sig.tracks), default=0.0)
            old_strength = "STRONG" if max_s >= 14.0 else \
                ("SIGNAL" if max_s >= 6.0 else "NONE")
            direction = old_dir; score = old_score
            strength = old_strength
            avg_edge = float(np.mean([
                st.sharpe * (st.wr_long if st.trend_dir == 1 else st.wr_short)
                for st in active_states])) if active_states else 0.0

        if direction != 0:
            scores_list.append(score); edges_list.append(avg_edge)

        # Entry
        if pos is None and direction != 0 and score >= entry_thresh:
            ep = pc["op"][bar_i] * 1.0003
            atr_v = pc["atrs"][bar_i] if pc["atrs"][bar_i] > 0 else ep * 0.02
            sp = ep - direction * cfg_stop * atr_v
            pos = dict(entry_price=ep, direction=direction, entry_bar=bar_i,
                       stop_price=sp, trail_active=False, trail_extreme=ep, tp1_done=False)

        # Exit
        if pos is not None:
            close = pc["cl"][bar_i]; high = pc["hi"][bar_i]; low = pc["lo"][bar_i]
            catr = pc["atrs"][bar_i] if pc["atrs"][bar_i] > 0 else pos["entry_price"] * 0.02
            held = bar_i - pos["entry_bar"]
            exit_reason = None; exit_px = None

            if held >= cfg_hold:
                exit_reason = "TIME_STOP"; exit_px = close
            elif direction != 0 and direction != pos["direction"]:
                exit_reason = "TREND_FLIP"; exit_px = close
            elif pos["direction"] == 1 and low <= pos["stop_price"]:
                exit_reason = "STOP_OUT"; exit_px = pos["stop_price"]
            elif pos["direction"] == -1 and high >= pos["stop_price"]:
                exit_reason = "STOP_OUT"; exit_px = pos["stop_price"]
            elif not pos["tp1_done"]:
                tp1_px = pos["entry_price"] + pos["direction"] * cfg_tp1 * catr
                if (pos["direction"] == 1 and close >= tp1_px) or \
                   (pos["direction"] == -1 and close <= tp1_px):
                    pos["stop_price"] = pos["entry_price"]
                    pos["trail_active"] = True
                    pos["trail_extreme"] = close
                    pos["tp1_done"] = True
            elif pos.get("trail_active") and pos.get("tp1_done"):
                if pos["direction"] == 1:
                    new_tr = max(pos["trail_extreme"], high) - cfg_trail * catr
                    if low <= new_tr:
                        exit_reason = "TRAIL_STOP"; exit_px = float(new_tr)
                    else:
                        pos["trail_extreme"] = float(max(pos["trail_extreme"], high))
                        pos["stop_price"] = new_tr
                else:
                    new_tr = min(pos["trail_extreme"], low) + cfg_trail * catr
                    if high >= new_tr:
                        exit_reason = "TRAIL_STOP"; exit_px = float(new_tr)
                    else:
                        pos["trail_extreme"] = float(min(pos["trail_extreme"], low))
                        pos["stop_price"] = new_tr

            if exit_reason is not None and exit_px is not None:
                gross = pos["direction"] * (exit_px - pos["entry_price"]) / pos["entry_price"]
                net = gross - 0.0005
                trades.append((pos["entry_bar"], bar_i, pos["direction"],
                               pos["entry_price"], exit_px, net, gross))
                eq_val *= (1 + net); pos = None

        equity.append(eq_val)

    if pos is not None:
        lp = pc["cl"][-1]
        gross = pos["direction"] * (lp - pos["entry_price"]) / pos["entry_price"]
        net = gross - 0.0005
        trades.append((pos["entry_bar"], n-1, pos["direction"],
                       pos["entry_price"], lp, net, gross))
        eq_val *= (1 + net); pos = None

    if not trades:
        return BMetrics(
            "pair", 0, 0.0, 0.0, 0.0, 0.0, 0.0,
            float(np.mean(scores_list)) if scores_list else 0.0,
            float(np.mean(edges_list)) if edges_list else 0.0)

    pnls = [t[5] for t in trades]
    winners = [p for p in pnls if p > 0]; losers = [p for p in pnls if p < 0]
    wr = round(len(winners) / len(pnls), 4)
    gross_sum = sum(t[6] for t in trades)
    pf = abs(gross_sum / sum(losers)) if losers else (999. if winners else 0.)
    eq_arr = np.array(equity, dtype=np.float64)
    rets = np.diff(eq_arr) / eq_arr[:-1]
    std_r = float(np.std(rets))
    sh = float(np.mean(rets) / std_r * np.sqrt(252 * 96)) if std_r > 0 else 0.0
    running_max = np.maximum.accumulate(eq_arr)
    max_dd = round(float(np.min((eq_arr / running_max - 1))), 4)

    return BMetrics(
        "pair", len(trades), wr, round(sh, 4), round(pf, 4),
        max_dd, round(eq_val - 1.0, 4),
        round(float(np.mean(scores_list)), 3) if scores_list else 0.0,
        round(float(np.mean(edges_list)), 4) if edges_list else 0.0)


ASSETS = ["BTCUSD", "ETHUSD"]
TIMEFRAMES = ["5m", "15m", "30m", "1h", "4h"]


if __name__ == "__main__":
    t0 = time.time()
    results = {}
    grand_new = {"sharpe": [], "win_rate": [], "pf": [], "edge": []}
    grand_old = {"sharpe": [], "win_rate": [], "pf": [], "edge": []}

    jobs = [(sym, tf) for sym in ASSETS for tf in TIMEFRAMES]
    total_jobs = len(jobs)
    run_i = 0

    print("Sterling v4 — Full Ensemble Comparison")
    print(f"  Jobs: {total_jobs}  |  Max bars: {MAX_BARS:,}  |  Sample: {SAMPLE}")
    print()

    for sym, tf in jobs:
        run_i += 1
        t_pair = time.time()
        sample_every = SAMPLE[tf]

        candles = load_candles(sym, tf, sample_every=sample_every, max_bars=MAX_BARS)
        n_c = len(candles)
        print(f"[{run_i}/{total_jobs}] {sym}/{tf}: {n_c:,} bars (sample={sample_every}x)")
        t_pre = time.time()
        pc = precompute(candles, regime_every=REGIME_EVERY)
        print(f"  precompute: {time.time()-t_pre:.1f}s")

        t_new = time.time()
        new_m = run_backtest(pc, candles, use_new=True)
        t_old = time.time()
        old_m = run_backtest(pc, candles, use_new=False)
        t_both = time.time()

        results[f"{sym}/{tf}"] = {
            "new": dict(trade_count=new_m.trade_count, win_rate=new_m.win_rate,
                        sharpe=new_m.sharpe, profit_factor=new_m.profit_factor,
                        max_drawdown=new_m.max_drawdown, cagr=new_m.cagr,
                        avg_score=new_m.avg_score, avg_edge=new_m.avg_edge),
            "old": dict(trade_count=old_m.trade_count, win_rate=old_m.win_rate,
                        sharpe=old_m.sharpe, profit_factor=old_m.profit_factor,
                        max_drawdown=old_m.max_drawdown, cagr=old_m.cagr,
                        avg_score=old_m.avg_score, avg_edge=old_m.avg_edge),
            "delta_sharpe": round(new_m.sharpe - old_m.sharpe, 4),
            "delta_wr": round(new_m.win_rate - old_m.win_rate, 4),
            "delta_pf": round(new_m.profit_factor - old_m.profit_factor, 4),
            "delta_edge": round(new_m.avg_edge - old_m.avg_edge, 4),
            "n_candles": n_c,
        }

        ds = results[f"{sym}/{tf}"]["delta_sharpe"]
        winner = "NEW" if ds > 0 else "OLD" if ds < 0 else "TIE"
        elapsed = time.time() - t_pair
        print(f"  NEW: {new_m.trade_count}d WR={new_m.win_rate:.0%} Sh={new_m.sharpe:+.2f} PF={new_m.profit_factor:.2f} Edge={new_m.avg_edge:.3f}")
        print(f"  OLD: {old_m.trade_count}d WR={old_m.win_rate:.0%} Sh={old_m.sharpe:+.2f} PF={old_m.profit_factor:.2f} Edge={old_m.avg_edge:.3f}")
        print(f"  ΔSh={ds:+.3f} [{winner}] | NEW={t_new-t_pair:.0f}s OLD={t_old-t_new:.0f}s total={elapsed:.0f}s")
        print()

        for m, grand_d in [(new_m, grand_new), (old_m, grand_old)]:
            if m.trade_count >= 5:
                grand_d["sharpe"].append(m.sharpe)
                grand_d["win_rate"].append(m.win_rate)
                grand_d["pf"].append(m.profit_factor)
                grand_d["edge"].append(m.avg_edge)

    # Summary
    print("=" * 75)
    print(f"{'Pair':12s}  {'NEW Sharpe':>10s}  {'OLD Sharpe':>10s}  {'ΔSharpe':>8s}  {'ΔWR':>6s}  {'ΔPF':>7s}  Winner")
    print("-" * 75)
    for key, r in sorted(results.items()):
        ds = r["delta_sharpe"]
        dw = r["delta_wr"]
        dp = r["delta_pf"]
        winner = "NEW" if ds > 0 else "OLD" if ds < 0 else "TIE"
        print(f"{key:12s}  {r['new']['sharpe']:>+10.3f}  {r['old']['sharpe']:>+10.3f}  "
              f"{ds:>+8.3f}  {dw:>+6.0%}  {dp:>+7.3f}  {winner}")

    print()
    if grand_new["sharpe"] and grand_old["sharpe"]:
        print(f"Aggregate ({len(grand_new['sharpe'])} pairs):")
        for label, grand in [("NEW", grand_new), ("OLD", grand_old)]:
            n = len(grand["sharpe"])
            print(f"  {label}: avgSharpe={sum(grand['sharpe'])/n:+.3f}  avgWR={sum(grand['win_rate'])/n:.1%}  "
                  f"avgPF={sum(grand['pf'])/n:.3f}  avgEdge={sum(grand['edge'])/n:.4f}")

    total_time = time.time() - t0
    print(f"\nTotal time: {total_time:.0f}s ({total_time/60:.1f} min)")

    out = Path(__file__).resolve().parent / "real_backtest_results.json"
    with open(out, "w") as f:
        json.dump({"results": results, "total_time_s": round(total_time, 1),
                   "params": dict(MAX_BARS=MAX_BARS, SAMPLE=SAMPLE,
                                  REGIME_EVERY=REGIME_EVERY, LOOKBACK=80)}, f, indent=2, default=str)
    print(f"Saved → {out}")