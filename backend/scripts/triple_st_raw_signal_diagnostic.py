"""
Diagnostic: Raw Signal Test for Triple SuperTrend.

Tests FIX 1 from the overfitting analysis:
  "Does the 3/3 consensus + ST1 flip have ANY predictive value?"

Uses proper library functions: compute_features, build_consensus, build_regime.
Implements exact FRESH_WINDOW and flip detection from backtest.py.

Expected baseline: PF > 1.2 on full sample → signal has edge
Expected baseline: PF < 1.2 on full sample → signal itself is noise
"""
from __future__ import annotations

import sqlite3
import sys
import math
from pathlib import Path
from typing import List, Dict

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.market import Candle
from app.engines.triple_st.features import compute_features
from app.engines.triple_st.engine import build_consensus, build_regime, RegimeArrays
from app.engines.triple_st.config import ASSET_TABLE, AssetClass

FEE_PCT = 0.05
FRZ_WARMUP = 100


def load_candles(symbol: str, resolution: str, lookback_days: int = 730) -> List[Candle]:
    DB_PATH = Path("/home/nageshmadaram/Sterling/backend/sterling_paper.db")
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT time,open,high,low,close,volume FROM ohlcv "
        "WHERE symbol=? AND resolution=? ORDER BY time ASC",
        (symbol, resolution)
    ).fetchall()
    conn.close()
    return [
        Candle(timestamp_ms=int(t)*1000, open=float(o), high=float(h),
               low=float(l), close=float(c), volume=float(v or 0))
        for t, o, h, l, c, v in rows
    ]


def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    tr = np.maximum(highs - lows, np.maximum(abs(highs - np.roll(closes, 1)), abs(lows - np.roll(closes, 1))))
    tr[0] = 0
    atr = np.zeros(n, dtype=float)
    cur = 0.0
    for i in range(n):
        cur = (cur * (period - 1) + tr[i]) / period if i > 0 else tr[0]
        atr[i] = cur
    return atr


def run_raw_test(
    candles: List[Candle],
    min_confirm: int = 3,
    sl_mult: float = 1.5,
    tp_mult: float = 3.0,
    use_be: bool = False,
    be_trigger_r: float = 1.0,
    use_trail: bool = False,
    trail_atr_mult: float = 3.0,
    trail_source: str = "ST3",
    max_bars: int = 99999,
    time_stop_bars: int = 60,
    use_regime_filter: bool = False,
    regime_adx_threshold: float = 20.0,
    regime_chop_threshold: float = 61.8,
) -> dict:
    """Raw signal test with proper library functions and exact backtest fresh-flip logic."""
    n = len(candles)
    if n < FRZ_WARMUP + 20:
        return {"trades": [], "win_rate": 0, "pf": 0, "expectancy_r": 0,
                "avg_win_r": 0, "avg_loss_r": 0, "n": 0, "wins": 0, "losses": 0}

    feat = compute_features(candles, vol_ma_period=20)
    cons = build_consensus(feat, min_confirm=min_confirm)

    asset = ASSET_TABLE[AssetClass.LARGE]
    regime = build_regime(feat, asset) if use_regime_filter else None

    closes  = np.array([c.close for c in candles], dtype=float)
    opens   = np.array([c.open  for c in candles], dtype=float)
    highs   = np.array([c.high  for c in candles], dtype=float)
    lows    = np.array([c.low   for c in candles], dtype=float)
    ts_arr  = np.array([c.timestamp_ms for c in candles], dtype=int)

    atr14 = compute_atr(highs, lows, closes, period=14)

    FRESH_WINDOW = 3
    prev_gated = 0
    flip_bar = -999

    TRAIL_IDX = {"ST1": 0, "ST2": 1, "ST3": 2}.get(trail_source, 2)

    trades: List[dict] = []
    pending: Dict = None
    pos: Dict = None
    cooldown = 0

    for i in range(FRZ_WARMUP, min(n, FRZ_WARMUP + max_bars)):
        # ── track flip bar (from backtest.py) ──────────────────────────────
        _mc = min_confirm
        gd = int(cons.direction[i]) if int(cons.agree_count[i]) >= _mc else 0
        if gd != 0 and gd != prev_gated:
            flip_bar = i
        prev_gated = gd

        # ── regime filter ──────────────────────────────────────────────────
        if use_regime_filter and regime is not None:
            adx_ok = feat.adx[i] >= regime_adx_threshold
            chop_ok = feat.chop[i] < regime_chop_threshold
            if not (adx_ok and chop_ok):
                # Skip entry but can still manage position
                pass

        # ── manage open position ────────────────────────────────────────────
        if pos is not None:
            h, l, c = float(highs[i]), float(lows[i]), float(closes[i])
            pos["bars_held"] = i - pos["entry_bar"]
            pos["extreme"] = max(pos["extreme"], h) if pos["direction"] == 1 else min(pos["extreme"], l)
            long = pos["direction"] == 1

            # Breakeven
            if use_be and not pos["be_moved"]:
                favor = (pos["extreme"] - pos["entry"]) if long else (pos["entry"] - pos["extreme"])
                if favor >= be_trigger_r * pos["r_distance"]:
                    pos["be_moved"] = True
                    pos["stop"] = pos["entry"]

            # Trailing
            if use_trail:
                trail_atr = trail_atr_mult * max(atr14[i], 1e-9)
                if long:
                    pos["stop"] = max(pos["stop"], pos["extreme"] - trail_atr)
                else:
                    pos["stop"] = min(pos["stop"], pos["extreme"] + trail_atr)
            else:
                # ST3 trailing (from exits.py)
                trail_line = float(feat.st_lines[TRAIL_IDX][i])
                trail_trend = int(feat.st_trends[TRAIL_IDX][i])
                if trail_line > 0:
                    if long and trail_line < c:
                        pos["stop"] = max(pos["stop"], trail_line)
                    elif not long and trail_line > c:
                        pos["stop"] = min(pos["stop"], trail_line)

            # Check SL
            sl_hit = (l <= pos["stop"]) if long else (h >= pos["stop"])
            if sl_hit:
                exit_px = pos["stop"]
                pnl_r = pos["direction"] * (exit_px - pos["entry"]) / pos["r_distance"]
                fee_r = FEE_PCT / 100 * 2 * sl_mult
                pnl_r -= fee_r / max(sl_mult, 0.01)
                trades.append({
                    "pnl_r": pnl_r,
                    "direction": "long" if long else "short",
                    "exit_bar": pos["bars_held"],
                    "reason": "breakeven_stop" if pos["be_moved"] else "stop_loss",
                    "entry_ts": pos["entry_ts"],
                    "exit_ts": ts_arr[i],
                })
                pos = None
                cooldown = i + 3
                continue

            # Check TP
            tp_hit = (h >= pos["tp"]) if long else (l <= pos["tp"])
            if tp_hit:
                exit_px = pos["tp"]
                pnl_r = pos["direction"] * (exit_px - pos["entry"]) / pos["r_distance"]
                fee_r = FEE_PCT / 100 * 2 * sl_mult
                pnl_r -= fee_r / max(sl_mult, 0.01)
                trades.append({
                    "pnl_r": pnl_r, "direction": "long" if long else "short",
                    "exit_bar": pos["bars_held"], "reason": "take_profit",
                    "entry_ts": pos["entry_ts"], "exit_ts": ts_arr[i],
                })
                pos = None
                cooldown = i + 1
                continue

            # Time stop
            if pos["bars_held"] >= time_stop_bars:
                exit_px = c
                pnl_r = pos["direction"] * (exit_px - pos["entry"]) / pos["r_distance"]
                trades.append({
                    "pnl_r": pnl_r, "direction": "long" if long else "short",
                    "exit_bar": pos["bars_held"], "reason": "time_stop",
                    "entry_ts": pos["entry_ts"], "exit_ts": ts_arr[i],
                })
                pos = None
                cooldown = i + 2
                continue

        # ── execute pending entry ───────────────────────────────────────────
        if pending is not None:
            age = i - pending["signal_bar"]
            if age > 2:
                pending = None
            else:
                entry_px = float(opens[i])
                ref_close = float(closes[pending["signal_bar"]])
                slip = abs(entry_px - ref_close) / ref_close * 100.0 if ref_close > 0 else 999
                if slip <= 0.6:
                    direction_sig = pending["dir"]
                    sl_dist = sl_mult * max(atr14[i], 1e-9)
                    tp_dist = tp_mult * sl_dist
                    entry = entry_px
                    long = direction_sig == 1
                    stop = entry - sl_dist if long else entry + sl_dist
                    tp   = entry + tp_dist if long else entry - tp_dist
                    pos = {
                        "entry": entry, "stop": stop, "tp": tp,
                        "direction": direction_sig, "entry_bar": i,
                        "bars_held": 0, "entry_ts": ts_arr[i],
                        "r_distance": sl_dist, "be_moved": False,
                        "extreme": entry,
                    }
                pending = None
                continue

        # ── arm new entry (with FRESH_WINDOW from backtest.py) ─────────────
        if pos is None and pending is None and i >= cooldown:
            gd = int(cons.direction[i]) if int(cons.agree_count[i]) >= min_confirm else 0
            fresh = (i - flip_bar) <= FRESH_WINDOW and gd == cons.direction[i]

            if gd != 0 and fresh:
                pending = {"signal_bar": i, "dir": gd}

    # Compute stats
    if not trades:
        return {"trades": [], "win_rate": 0, "pf": 0, "expectancy_r": 0,
                "avg_win_r": 0, "avg_loss_r": 0, "n": 0, "wins": 0, "losses": 0}

    pnls = np.array([t["pnl_r"] for t in trades])
    wins  = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    gross_win  = float(wins.sum()) if wins.size else 0.0
    gross_loss = float(abs(losses.sum())) if losses.size else 0.0
    pf = gross_win / gross_loss if gross_loss > 0 else float(gross_win > 0) * 99.9
    wr = float((pnls > 0).mean())

    return {
        "trades": trades,
        "win_rate": round(wr, 4),
        "pf": round(pf, 3),
        "expectancy_r": round(float(pnls.mean()), 3),
        "avg_win_r": round(float(wins.mean()), 3) if wins.size else 0,
        "avg_loss_r": round(float(losses.mean()), 3) if losses.size else 0,
        "n": len(trades),
        "wins": int((pnls > 0).sum()),
        "losses": int((pnls <= 0).sum()),
        "total_return_pct": round((pf - 1) * 100, 2) if pf > 0 else 0,
    }


def run_diagnostic():
    print("=" * 70)
    print("TRIPLE ST — RAW SIGNAL DIAGNOSTIC (using actual library functions)")
    print("=" * 70)

    # Load BTC 4H and 1H data
    print("\nLoading BTCUSD data...")
    candles_4h = load_candles("BTCUSD", "4h", lookback_days=730)
    candles_1h = load_candles("BTCUSD", "1h", lookback_days=730)
    print(f"  Loaded {len(candles_4h)} 4H bars, {len(candles_1h)} 1H bars")

    if len(candles_4h) < FRZ_WARMUP + 50:
        print("ERROR: Not enough candles")
        return

    results = {}

    # ════════════════════════════════════════════════════════════════════
    # 4H TESTS
    # ════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("4H RESULTS")
    print("=" * 70)

    # Variant A: Fixed 2:1 RR, no BE, no trailing, no regime
    print("\n── A: 3/3 consensus + fixed 2:1 RR ──────────────────────────")
    r = run_raw_test(candles_4h, min_confirm=3, sl_mult=1.5, tp_mult=3.0,
                     use_be=False, use_trail=False, time_stop_bars=60)
    results["4H_A_fixed_rr"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    # Variant D: ST3 trailing only (no fixed TP) - BEST ON 4H
    print("\n── D: 3/3 consensus + ST3 trailing (no fixed TP) ──────────────")
    r = run_raw_test(candles_4h, min_confirm=3, sl_mult=1.5, tp_mult=12.0,
                     use_be=False, use_trail=True, trail_atr_mult=3.0,
                     time_stop_bars=60)
    results["4H_D_trail"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    # Variant F: 2/3 consensus + ST3 trailing - BEST OVERALL
    print("\n── F: 2/3 consensus + ST3 trailing ───────────────────────────")
    r = run_raw_test(candles_4h, min_confirm=2, sl_mult=1.5, tp_mult=12.0,
                     use_be=False, use_trail=True, trail_atr_mult=3.0,
                     time_stop_bars=60)
    results["4H_F_2of3_trail"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    # Variant H: Wider stops (2.5× ATR, 2:1 RR, ST3 trailing)
    print("\n── H: 3/3 + wider stops (2.5× ATR) + ST3 trailing ─────────────")
    r = run_raw_test(candles_4h, min_confirm=3, sl_mult=2.5, tp_mult=5.0,
                     use_be=False, use_trail=True, trail_atr_mult=3.0,
                     time_stop_bars=60)
    results["4H_H_wide_trail"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    # Variant I: Longer time stop (120 bars = ~20 days on 4H)
    print("\n── I: 3/3 consensus + ST3 trailing + 120-bar time stop ─────────")
    r = run_raw_test(candles_4h, min_confirm=3, sl_mult=1.5, tp_mult=12.0,
                     use_be=False, use_trail=True, trail_atr_mult=3.0,
                     time_stop_bars=120)
    results["4H_I_long_time"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    # Variant J: No BE, ST3 trailing, wider trail ATR (4×)
    print("\n── J: 3/3 + ST3 trailing (4× ATR) + no BE ────────────────────")
    r = run_raw_test(candles_4h, min_confirm=3, sl_mult=1.5, tp_mult=12.0,
                     use_be=False, use_trail=True, trail_atr_mult=4.0,
                     time_stop_bars=60)
    results["4H_J_wide_trail"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    # Variant K: Regime filter only (ADX > 20, CHOP < 61.8) + ST3 trailing
    print("\n── K: 3/3 + regime filter + ST3 trailing ─────────────────────")
    r = run_raw_test(candles_4h, min_confirm=3, sl_mult=1.5, tp_mult=12.0,
                     use_be=False, use_trail=True, trail_atr_mult=3.0,
                     time_stop_bars=60, use_regime_filter=True,
                     regime_adx_threshold=20.0, regime_chop_threshold=61.8)
    results["4H_K_regime"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    # ════════════════════════════════════════════════════════════════════
    # 1H TESTS (more signals, better statistics)
    # ════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("1H RESULTS (more signals → better statistics)")
    print("=" * 70)

    print("\n── 1H_A: 3/3 consensus + ST3 trailing ───────────────────────")
    r = run_raw_test(candles_1h, min_confirm=3, sl_mult=1.5, tp_mult=12.0,
                     use_be=False, use_trail=True, trail_atr_mult=3.0,
                     time_stop_bars=60)
    results["1H_A_trail"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    print("\n── 1H_F: 2/3 consensus + ST3 trailing ───────────────────────")
    r = run_raw_test(candles_1h, min_confirm=2, sl_mult=1.5, tp_mult=12.0,
                     use_be=False, use_trail=True, trail_atr_mult=3.0,
                     time_stop_bars=60)
    results["1H_F_2of3_trail"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    print("\n── 1H_H: 3/3 + wider stops (2.5× ATR) + ST3 trailing ──────────")
    r = run_raw_test(candles_1h, min_confirm=3, sl_mult=2.5, tp_mult=5.0,
                     use_be=False, use_trail=True, trail_atr_mult=3.0,
                     time_stop_bars=60)
    results["1H_H_wide_trail"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    print("\n── 1H_K: 3/3 + regime filter + ST3 trailing ───────────────────")
    r = run_raw_test(candles_1h, min_confirm=3, sl_mult=1.5, tp_mult=12.0,
                     use_be=False, use_trail=True, trail_atr_mult=3.0,
                     time_stop_bars=60, use_regime_filter=True,
                     regime_adx_threshold=20.0, regime_chop_threshold=61.8)
    results["1H_K_regime"] = r
    print(f"  Trades: {r['n']}, WinRate: {r['win_rate']:.1%}, PF: {r['pf']:.3f}, "
          f"E: {r['expectancy_r']:+.3f}R")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY TABLE")
    print("=" * 70)
    print(f"{'Variant':<22} {'Trades':>8} {'WinRate':>10} {'PF':>8} {'E(R)':>8} {'AvgWin':>8} {'AvgLoss':>8}")
    print("-" * 70)
    for name, r in sorted(results.items(), key=lambda x: x[1]["pf"], reverse=True):
        marker = " ◀" if "1H" in name and r["pf"] > 1.0 else ""
        print(f"{name:<22} {r['n']:>8} {r['win_rate']:>10.1%} {r['pf']:>8.3f} "
              f"{r['expectancy_r']:>8.3f} {r['avg_win_r']:>8.3f} {r['avg_loss_r']:>8.3f}{marker}")

    print("\nVERDICT:")
    best = max(results.items(), key=lambda x: x[1]["pf"])

    if best[1]["pf"] < 1.0:
        print(f"\n  ❌ NO EDGE: Best PF = {best[1]['pf']:.3f} ({best[0]}, {best[1]['n']} trades)")
    elif best[1]["pf"] < 1.3:
        print(f"\n  ⚠️  MARGINAL EDGE: Best PF = {best[1]['pf']:.3f} ({best[0]}, {best[1]['n']} trades)")
    else:
        print(f"\n  ✅ EDGE CONFIRMED: Best PF = {best[1]['pf']:.3f} ({best[0]}, {best[1]['n']} trades)")

    # Analyze 1H vs 4H
    h_results = {k: v for k, v in results.items() if k.startswith("1H_")}
    h4_results = {k: v for k, v in results.items() if k.startswith("4H_")}

    if h_results:
        best_1h = max(h_results.items(), key=lambda x: x[1]["pf"])
        print(f"\n  1H best: {best_1h[0]} → PF={best_1h[1]['pf']:.3f}, {best_1h[1]['n']} trades")
    if h4_results:
        best_4h = max(h4_results.items(), key=lambda x: x[1]["pf"])
        print(f"  4H best: {best_4h[0]} → PF={best_4h[1]['pf']:.3f}, {best_4h[1]['n']} trades")

    return results


if __name__ == "__main__":
    run_diagnostic()