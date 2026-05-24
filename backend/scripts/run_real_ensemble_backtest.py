#!/usr/bin/env python3
"""
Sterling v4 — Fast Real-Data Backtest (profiling first pass)
===========================================================
Only BTCUSD/15m with 500 bars to verify the infrastructure works
and get real-data metrics quickly. Then scale up.
"""
from __future__ import annotations
import os, sys, json, sqlite3, time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np

from app.schemas.market import Candle
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.tracks.base import TrackSignal, NEUTRAL_TRACK_SIGNAL
from app.engines.directional.tracks.trend_following import TrendFollowingTrack
from app.engines.directional.tracks.vcp_track import VCPTrack, VCPTrackConfig
from app.engines.directional.tracks.fade_extremes import FadeExtremesTrack
from app.engines.directional.track_scoring import (
    compute_ensemble_signal, _TRACK_WINDOWS, _WIN_REGISTRY, _REGIME_WEIGHT,
)
from app.engines.hybrid_vcp.profiles import PROFILES


DB_PATH = Path(__file__).resolve().parent.parent / "sterling_paper.db"

RES_MAP = {"5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h"}


def load_candles(symbol: str, resolution: str, n: int = 800) -> list:
    uri = f"file:{DB_PATH}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, timeout=60.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    db_res = RES_MAP.get(resolution, resolution.lower())
    rows = cur.execute(
        'SELECT * FROM ohlcv WHERE symbol=? AND resolution=? ORDER BY time DESC LIMIT ?',
        (symbol.upper(), db_res, n)
    ).fetchall()
    conn.close()
    rows = list(reversed(rows))
    return [Candle(
        timestamp_ms=r["time"] * 1000,
        open=float(r["open"]), high=float(r["high"]),
        low=float(r["low"]), close=float(r["close"]),
        volume=float(r["volume"]),
    ) for r in rows]


def compute_atr(highs, lows, closes, period=14):
    n = len(closes)
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
    atrs = np.zeros(n)
    atrs[period] = float(np.mean(tr[1:period+1]))
    for i in range(period+1, n):
        atrs[i] = (atrs[i-1] * (period-1) + tr[i]) / period
    return atrs


@dataclass
class BMetrics:
    label: str
    trade_count: int; win_rate: float; sharpe: float
    profit_factor: float; max_drawdown: float; cagr: float
    avg_score: float; avg_edge: float


def run_backtest(
    candles: list,
    profile_label: str,
    use_new: bool,
    entry_thresh: float = 7.0,
) -> BMetrics:
    _TRACK_WINDOWS.clear()
    n = len(candles)
    if n < 60:
        return BMetrics(profile_label, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    op = np.array([c.open  for c in candles], dtype=np.float64)
    hi = np.array([c.high  for c in candles], dtype=np.float64)
    lo = np.array([c.low   for c in candles], dtype=np.float64)
    cl = np.array([c.close for c in candles], dtype=np.float64)
    atrs = compute_atr(hi, lo, cl)

    cfg_stop  = 2.0; cfg_tp1 = 1.5; cfg_trail = 3.0; cfg_hold = 30

    tf_t = TrendFollowingTrack()
    vc_t = VCPTrack(VCPTrackConfig(profile_key="btc_scalping_15m"))
    mr_t = FadeExtremesTrack()
    track_map = {"trend_following": tf_t, "vcp": vc_t, "mean_reversion": mr_t}

    equity = [1.0]; eq_val = 1.0
    pos = None
    trades = []
    scores_list = []; edges_list = []
    strong_count = 0

    for bar_i in range(40, n):
        lookback = candles[max(0, bar_i - 150):bar_i]
        if len(lookback) < 40:
            continue
        r_label = get_regime_label(lookback)
        try:
            r_obj = compute_regime(
                lookback[-100:] if len(lookback) >= 100 else lookback,
                macro_filter="adx_4h"
            )
        except:
            r_obj = None

        cands = []
        for nm in ["trend_following", "vcp", "mean_reversion"]:
            try:
                cands.append(track_map[nm].compute(lookback, r_obj))
            except:
                cands.append(NEUTRAL_TRACK_SIGNAL)

        sig = compute_ensemble_signal(cands, regime_label=r_label)

        if use_new:
            direction = sig.direction; score = sig.ensemble_score; strength = sig.strength
            avg_edge = sig.edge_per_trade
        else:
            # OLD strategy
            active_states = [st for st in sig.tracks if st.trend_dir != 0]
            total_w = sum(st.weight for st in active_states)
            n_active = len(active_states)
            old_dir = int(np.sign(sum(st.weight * st.trend_dir for st in active_states))) if (total_w > 0 and n_active > 0) else 0
            old_score = (total_w / n_active * 20.0) if n_active > 0 else 0.0
            max_s = max((st.raw_score for st in sig.tracks), default=0.0)
            old_strength = "STRONG" if max_s >= 14.0 else ("SIGNAL" if max_s >= 6.0 else "NONE")
            direction = old_dir; score = old_score; strength = old_strength
            avg_edge = float(np.mean([st.sharpe * (st.wr_long if st.trend_dir == 1 else st.wr_short) for st in active_states])) if active_states else 0.0

        if direction != 0:
            scores_list.append(score); edges_list.append(avg_edge)
        if strength == "STRONG":
            strong_count += 1

        # Entry
        if pos is None and direction != 0 and score >= entry_thresh:
            ep = float(op[bar_i]) * 1.0003
            atr_v = float(atrs[bar_i]) if atrs[bar_i] > 0 else ep * 0.02
            sp = ep - direction * cfg_stop * atr_v
            pos = dict(entry_price=ep, direction=direction, entry_bar=bar_i,
                       stop_price=sp, trail_active=False, trail_extreme=ep, tp1_done=False)

        # Exit
        if pos is not None:
            close = float(cl[bar_i]); high = float(hi[bar_i]); low = float(lo[bar_i])
            catr = float(atrs[bar_i]) if atrs[bar_i] > 0 else pos["entry_price"] * 0.02
            held = bar_i - pos["entry_bar"]
            exit_reason = None; exit_px = None

            if held >= cfg_hold:
                exit_reason = "TIME_STOP"; exit_px = close
            elif direction != 0 and direction != pos["direction"]:
                exit_reason = "TREND_FLIP"; exit_px = close
            elif pos["direction"] == 1 and low <= pos["stop_price"]:
                exit_reason = "STOP_OUT"; exit_px = float(pos["stop_price"])
            elif pos["direction"] == -1 and high >= pos["stop_price"]:
                exit_reason = "STOP_OUT"; exit_px = float(pos["stop_price"])
            elif not pos["tp1_done"]:
                tp1_px = pos["entry_price"] + pos["direction"] * cfg_tp1 * catr
                if (pos["direction"] == 1 and close >= tp1_px) or (pos["direction"] == -1 and close <= tp1_px):
                    pos["stop_price"] = pos["entry_price"]
                    pos["trail_active"] = True; pos["trail_extreme"] = close; pos["tp1_done"] = True
            elif pos.get("trail_active") and pos.get("tp1_done"):
                if pos["direction"] == 1:
                    new_tr = max(pos["trail_extreme"], high) - cfg_trail * catr
                    if low <= new_tr:
                        exit_reason = "TRAIL_STOP"; exit_px = float(new_tr)
                    else:
                        pos["trail_extreme"] = float(max(pos["trail_extreme"], high)); pos["stop_price"] = new_tr
                else:
                    new_tr = min(pos["trail_extreme"], low) + cfg_trail * catr
                    if high >= new_tr:
                        exit_reason = "TRAIL_STOP"; exit_px = float(new_tr)
                    else:
                        pos["trail_extreme"] = float(min(pos["trail_extreme"], low)); pos["stop_price"] = new_tr

            if exit_reason is not None and exit_px is not None:
                gross = pos["direction"] * (exit_px - pos["entry_price"]) / pos["entry_price"]
                net = gross - 0.0005
                trades.append((pos["entry_bar"], bar_i, pos["direction"], pos["entry_price"], exit_px, net, gross))
                eq_val *= (1 + net); pos = None

        equity.append(eq_val)

    if pos is not None:
        lp = float(cl[-1])
        gross = pos["direction"] * (lp - pos["entry_price"]) / pos["entry_price"]
        net = gross - 0.0005
        trades.append((pos["entry_bar"], n-1, pos["direction"], pos["entry_price"], lp, net, gross))
        eq_val *= (1 + net); pos = None

    if not trades:
        return BMetrics(profile_label, 0, 0.0, 0.0, 0.0, 0.0, 0.0,
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
        profile_label, len(trades), wr, round(sh, 4), round(pf, 4),
        max_dd, round(eq_val - 1.0, 4),
        round(float(np.mean(scores_list)), 3),
        round(float(np.mean(edges_list)), 4),
    )


def get_regime_label(candles):
    if len(candles) < 30:
        return "neutral"
    r = compute_regime(candles[-200:] if len(candles) >= 200 else candles, macro_filter="adx_4h")
    return r.macro_regime.value.lower() if r else "neutral"


# ── Quick test: BTCUSD/15m, 500 bars, both strategies ──────────────────────────

if __name__ == "__main__":
    t0 = time.time()
    print("Sterling v4 — Fast Real-Data Backtest")
    print()

    sym, tf = "BTCUSD", "15m"
    profile_label = "btc_scalping_15m"

    print(f"Loading candles for {sym}/{tf}...")
    candles = load_candles(sym, tf, n=800)
    n_c = len(candles)
    start_d = candles[0].timestamp_ms
    end_d = candles[-1].timestamp_ms
    print(f"  {n_c} candles, from {start_d} to {end_d}")
    print(f"  bar_i range for backtest: 40 to {n_c}")

    est_time = (n_c - 40) * 0.011
    print(f"  Estimated time: {est_time:.0f}s per strategy")

    print(f"\nRunning NEW strategy (by_edge+max+linear_agree)...")
    new_m = run_backtest(candles, profile_label, use_new=True)
    print(f"  {new_m.trade_count}d  WR={new_m.win_rate:.0%}  Sh={new_m.sharpe:.2f}  PF={new_m.profit_factor:.2f}  DD={new_m.max_drawdown:.0%}  Edge={new_m.avg_edge:.3f}  AvgScore={new_m.avg_score:.1f}")

    print(f"\nRunning OLD strategy (unweighted+mean+none)...")
    old_m = run_backtest(candles, profile_label, use_new=False)
    print(f"  {old_m.trade_count}d  WR={old_m.win_rate:.0%}  Sh={old_m.sharpe:.2f}  PF={old_m.profit_factor:.2f}  DD={old_m.max_drawdown:.0%}  Edge={old_m.avg_edge:.3f}  AvgScore={old_m.avg_score:.1f}")

    print(f"\n  ΔSharpe: {new_m.sharpe - old_m.sharpe:+.3f}")
    print(f"  ΔWR:     {new_m.win_rate - old_m.win_rate:+.0%}")
    print(f"  ΔPF:     {new_m.profit_factor - old_m.profit_factor:+.3f}")
    print(f"  ΔEdge:   {new_m.avg_edge - old_m.avg_edge:+.4f}")
    print(f"\n  Total time: {time.time()-t0:.1f}s")

    # Save
    out = Path(__file__).resolve().parent / "real_backtest_results.json"
    with open(out, "w") as f:
        json.dump({
            "test": f"{sym}/{tf}",
            "n_candles": n_candles,
            "new": {"trade_count": new_m.trade_count, "win_rate": new_m.win_rate,
                    "sharpe": new_m.sharpe, "profit_factor": new_m.profit_factor,
                    "max_drawdown": new_m.max_drawdown, "cagr": new_m.cagr,
                    "avg_score": new_m.avg_score, "avg_edge": new_m.avg_edge},
            "old": {"trade_count": old_m.trade_count, "win_rate": old_m.win_rate,
                    "sharpe": old_m.sharpe, "profit_factor": old_m.profit_factor,
                    "max_drawdown": old_m.max_drawdown, "cagr": old_m.cagr,
                    "avg_score": old_m.avg_score, "avg_edge": old_m.avg_edge},
            "delta_sharpe": round(new_m.sharpe - old_m.sharpe, 4),
            "delta_wr": round(new_m.win_rate - old_m.win_rate, 4),
            "delta_pf": round(new_m.profit_factor - old_m.profit_factor, 4),
        }, f, indent=2, default=str)
    print(f"Saved → {out}")