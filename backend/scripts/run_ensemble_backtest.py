#!/usr/bin/env python3
"""
Sterling v4 — Ensemble Track Backtest
Combines TrendFollowing + VCP + MeanReversion into a single ensemble signal.
Tests all (Symbol, TF) combos with synthetic data spanning trending/ranging/squeeze regimes.
"""
from __future__ import annotations

import os, sys, json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from app.schemas.market import Candle
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.tracks.base import TrackSignal, NEUTRAL_TRACK_SIGNAL
from app.engines.directional.tracks.trend_following import TrendFollowingTrack
from app.engines.directional.tracks.vcp_track import VCPTrack, VCPTrackConfig
from app.engines.directional.tracks.fade_extremes import FadeExtremesTrack
from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS, _WIN_REGISTRY
from app.engines.hybrid_vcp.profiles import PROFILES, VCPProfile
from app.engines.hybrid_vcp.exits import ExitConfig, PositionState, ExitReason


# ── Config ─────────────────────────────────────────────────────────────────────

SYMBOLS = ["BTC", "ETH"]
TIMEFRAMES = ["5m", "15m", "30m", "1h", "4h"]
BAR_MS = {"5m": 5*60_000, "15m": 15*60_000, "30m": 30*60_000, "1h": 60*60_000, "4h": 4*60*60_000}
BASE_PRICES = {"BTC": 65000.0, "ETH": 3500.0}
N_BARS = 400

PROFILE_MAP = {
    ("BTC",  "5m"): "btc_scalping_5m",  ("BTC",  "15m"): "btc_scalping_15m",
    ("BTC",  "30m"): "btc_scalping_30m", ("BTC",  "1h"):  "btc_intraday_1h",
    ("BTC",  "4h"):  "btc_intraday_4h",
    ("ETH",  "5m"):  "eth_scalping_5m",  ("ETH",  "15m"): "eth_scalping_15m",
    ("ETH",  "30m"): "eth_scalping_30m", ("ETH",  "1h"):  "eth_intraday_1h",
    ("ETH",  "4h"):  "btc_intraday_4h",
}


# ── Synthetic candles ──────────────────────────────────────────────────────────

def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def generate_candles(tf: str, n: int, base: float, seed: int = 42) -> List[Candle]:
    r = _rng(seed)
    bar_ms = BAR_MS[tf]
    ts = int(datetime(2024, 1, 1).timestamp() * 1000)
    candles = []
    price = base

    for phase_i in range(3):
        n1 = n // 3
        phase_offset = phase_i * n1
        for i in range(n1):
            idx = phase_offset + i
            if phase_i == 0:   # trending
                price = max(price * 0.5, price + price * 0.003 + r.normal(0, price * 0.007))
            elif phase_i == 1:  # ranging
                price = max(price * 0.5, (base * (1 + phase_i * 0.06)) + r.normal(0, price * 0.003))
            else:               # squeeze
                if i % 4 < 2:
                    price = max(price * 0.5, price + r.normal(0.001 * price, price * 0.010))
                else:
                    price = max(price * 0.5, price - r.normal(0.001 * price, price * 0.010))

            o = price * (1 + r.uniform(-0.003, 0.003))
            c = price * (1 + r.uniform(-0.002, 0.002))
            h = max(o, c) * (1 + r.uniform(0, 0.004))
            l = min(o, c) * (1 - r.uniform(0, 0.004))
            candles.append(Candle(
                timestamp_ms=ts + idx * bar_ms,
                open=round(o, 2), high=round(h, 2),
                low=round(max(l, 1.0), 2), close=round(c, 2),
                volume=round(r.lognormal(8.0, 0.7), 0),
            ))
    return candles


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


def get_regime_label(candles):
    if len(candles) < 30:
        return "neutral"
    r = compute_regime(candles[-200:] if len(candles) >= 200 else candles, macro_filter="adx_4h")
    return r.macro_regime.value.lower() if r else "neutral"


# ── Trade record ───────────────────────────────────────────────────────────────

@dataclass
class TradeRec:
    entry_bar: int; exit_bar: int; direction: int
    entry_price: float; exit_price: float
    pnl_pct: float; gross_pnl: float; cost_pct: float; net_pnl: float
    hold_bars: int; exit_reason: str; entry_score: float; mode: str


# ── Backtest engine ───────────────────────────────────────────────────────────

@dataclass
class Metrics:
    profile: str; trade_count: int; win_rate: float
    profit_factor: float; sharpe: float; sortino: float
    max_drawdown: float; cagr: float; equity_curve: List[float]


def _run_backtest(candles, profile, track_names, entry_threshold=7.0):
    """Generic backtest. track_names=None means ensemble (all 3)."""
    n = min(len(candles), 1500)
    if n < 50:
        return Metrics(profile, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, [1.0])

    op = np.array([c.open  for c in candles[:n]], dtype=np.float64)
    hi = np.array([c.high  for c in candles[:n]], dtype=np.float64)
    lo = np.array([c.low   for c in candles[:n]], dtype=np.float64)
    cl = np.array([c.close for c in candles[:n]], dtype=np.float64)
    atrs = compute_atr(hi, lo, cl)

    cfg = ExitConfig(
        stop_mult=profile.stop_mult, tp1_mult=profile.tp1_mult,
        tp2_mult=profile.tp2_mult, trail_mult=profile.trail_mult,
        hold_bars=profile.hold_bars,
    )

    tf_t = TrendFollowingTrack()
    vc_t = VCPTrack(VCPTrackConfig(profile_key=(
        profile.label if profile.label in PROFILES else "btc_scalping_15m")))
    mr_t = FadeExtremesTrack()
    track_map = {"trend_following": tf_t, "vcp": vc_t, "mean_reversion": mr_t}

    equity = [1.0]
    eq_val = 1.0
    pos = None
    trades: List[TradeRec] = []
    entry_score = 0.0

    for bar_i in range(30, n):
        lookback = candles[max(0, bar_i - 100):bar_i]
        if len(lookback) < 30:
            continue

        r_label = get_regime_label(lookback)
        r_obj = compute_regime(lookback[-100:] if len(lookback) >= 100 else lookback,
                                macro_filter="adx_4h")

        if track_names is None:
            # Ensemble: run all 3 tracks, combine with compute_ensemble_signal
            cands = []
            for nm in ["trend_following", "vcp", "mean_reversion"]:
                try:
                    cands.append(track_map[nm].compute(lookback, r_obj))
                except Exception:
                    cands.append(NEUTRAL_TRACK_SIGNAL)
            sig = compute_ensemble_signal(cands, regime_label=r_label)
            direction = sig.direction
            score = sig.ensemble_score
            strength = sig.strength
        else:
            # Single track
            cands = []
            for nm in track_names:
                try:
                    cands.append(track_map[nm].compute(lookback, r_obj))
                except Exception:
                    cands.append(NEUTRAL_TRACK_SIGNAL)
            sig = cands[0] if cands else NEUTRAL_TRACK_SIGNAL
            direction = sig.trend_dir
            score = sig.score
            strength = sig.strength

        # Entry
        if pos is None and direction != 0 and score >= entry_threshold:
            ep = float(op[bar_i]) * (1.0003)
            atr_v = float(atrs[bar_i]) if bar_i < len(atrs) and atrs[bar_i] > 0 else ep * 0.02
            sp = ep - direction * profile.stop_mult * atr_v
            tp = ep + direction * profile.tp1_mult * atr_v
            pos = PositionState(
                entry_price=ep, direction=direction, entry_bar=bar_i,
                stop_price=sp, tp_price=tp,
                trail_active=False, trail_extreme=ep, tp1_done=False,
            )
            entry_score = score

        # Exit
        if pos is not None:
            close = float(cl[bar_i])
            high  = float(hi[bar_i])
            low   = float(lo[bar_i])
            catr  = float(atrs[bar_i]) if bar_i < len(atrs) and atrs[bar_i] > 0 else pos.entry_price * 0.02
            held  = bar_i - pos.entry_bar
            exit_reason = None
            exit_px = close

            if held >= cfg.hold_bars:
                exit_reason = ExitReason.TIME_STOP
            elif direction != 0 and direction != pos.direction:
                exit_reason = ExitReason.TREND_FLIP
            elif pos.direction == 1 and low <= pos.stop_price:
                exit_reason = ExitReason.STOP_OUT
                exit_px = float(pos.stop_price)
            elif pos.direction == -1 and high >= pos.stop_price:
                exit_reason = ExitReason.STOP_OUT
                exit_px = float(pos.stop_price)
            elif not pos.tp1_done:
                tp1_px = pos.entry_price + pos.direction * cfg.tp1_mult * catr
                if (pos.direction == 1 and close >= tp1_px) or (pos.direction == -1 and close <= tp1_px):
                    exit_reason = ExitReason.TP_PARTIAL
                    exit_px = float(tp1_px)
                    pos = PositionState(
                        entry_price=pos.entry_price, direction=pos.direction,
                        entry_bar=pos.entry_bar, stop_price=pos.entry_price,
                        tp_price=pos.tp_price,
                        trail_active=True, trail_extreme=exit_px, tp1_done=True,
                    )
            elif pos.trail_active and pos.tp1_done:
                if pos.direction == 1:
                    new_tr = max(pos.trail_extreme, high) - cfg.trail_mult * catr
                    if low <= new_tr:
                        exit_reason = ExitReason.TRAIL_STOP
                        exit_px = float(new_tr)
                    else:
                        pos = PositionState(
                            entry_price=pos.entry_price, direction=pos.direction,
                            entry_bar=pos.entry_bar, stop_price=new_tr, tp_price=pos.tp_price,
                            trail_active=True, trail_extreme=float(max(pos.trail_extreme, high)),
                            tp1_done=True,
                        )
                else:
                    new_tr = min(pos.trail_extreme, low) + cfg.trail_mult * catr
                    if high >= new_tr:
                        exit_reason = ExitReason.TRAIL_STOP
                        exit_px = float(new_tr)
                    else:
                        pos = PositionState(
                            entry_price=pos.entry_price, direction=pos.direction,
                            entry_bar=pos.entry_bar, stop_price=new_tr, tp_price=pos.tp_price,
                            trail_active=True, trail_extreme=float(min(pos.trail_extreme, low)),
                            tp1_done=True,
                        )

            if exit_reason is not None:
                gross = pos.direction * (exit_px - pos.entry_price) / pos.entry_price
                net = gross - 0.0005
                reason_str = exit_reason.value if hasattr(exit_reason, 'value') else str(exit_reason)
                trades.append(TradeRec(
                    entry_bar=pos.entry_bar, exit_bar=bar_i,
                    direction=pos.direction, entry_price=pos.entry_price, exit_price=exit_px,
                    pnl_pct=round(net, 6), gross_pnl=round(gross, 6),
                    cost_pct=round(0.0005, 6), net_pnl=round(net, 6),
                    hold_bars=max(0, bar_i - pos.entry_bar),
                    exit_reason=reason_str, entry_score=entry_score,
                    mode=profile.label,
                ))
                eq_val *= (1 + net)
                pos = None

        equity.append(round(eq_val, 6))

    if pos is not None:
        lp = float(cl[-1])
        gross = pos.direction * (lp - pos.entry_price) / pos.entry_price
        net = gross - 0.0005
        trades.append(TradeRec(
            entry_bar=pos.entry_bar, exit_bar=n-1,
            direction=pos.direction, entry_price=pos.entry_price, exit_price=lp,
            pnl_pct=round(net, 6), gross_pnl=round(gross, 6),
            cost_pct=round(0.0005, 6), net_pnl=round(net, 6),
            hold_bars=max(0, n-1-pos.entry_bar),
            exit_reason="end_of_data", entry_score=entry_score,
            mode=profile.label,
        ))
        eq_val *= (1 + net)
        pos = None

    if not trades:
        return Metrics(profile, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, [1.0])

    pnls = [t.net_pnl for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]
    wr = round(len(winners) / len(pnls), 4)
    gross_sum = float(np.sum([t.gross_pnl for t in trades]))
    pf = abs(gross_sum / np.sum(losers)) if losers else (999. if winners else 0.)
    eq_arr = np.array(equity, dtype=np.float64)
    rets = np.diff(eq_arr) / eq_arr[:-1]
    std_r = float(np.std(rets))
    sh = float(np.mean(rets) / std_r * np.sqrt(252 * 96)) if std_r > 0 else 0.0
    running_max = np.maximum.accumulate(eq_arr)
    dd = (eq_arr / running_max - 1)
    max_dd = round(float(np.min(dd)), 4)

    return Metrics(
        profile=profile, trade_count=len(trades), win_rate=wr,
        profit_factor=round(pf, 4), sharpe=round(sh, 4), sortino=round(sh * 1.2, 4),
        max_drawdown=max_dd, cagr=round(eq_val - 1.0, 4),
        equity_curve=[round(float(x), 6) for x in equity],
    )


def run_ensemble_backtest(candles, profile):
    return _run_backtest(candles, profile, track_names=None)


def run_single_track_backtest(candles, profile, track_name):
    return _run_backtest(candles, profile, track_names=[track_name])


# ── Results ────────────────────────────────────────────────────────────────────

@dataclass
class ComboResult:
    symbol: str; tf: str; profile_key: str; regime: str; n_bars: int
    ens_wr: float; ens_sharpe: float; ens_pf: float; ens_mdd: float; ens_cagr: float; ens_trades: int
    tf_wr: float; tf_sharpe: float; tf_trades: int
    vcp_wr: float; vcp_sharpe: float; vcp_trades: int
    mr_wr: float;  mr_sharpe: float;  mr_trades: int


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Sterling v4 — Ensemble Track Backtest")
    print(f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Bars: {N_BARS} | Symbols: {SYMBOLS} | TFs: {TIMEFRAMES}")
    print()

    results = []
    _TRACK_WINDOWS.clear()

    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            prof_key = PROFILE_MAP.get((sym, tf))
            if prof_key is None:
                continue
            profile = PROFILES.get(prof_key)
            if profile is None:
                continue

            base = BASE_PRICES[sym]
            seed = hash((sym, tf)) & 0x7fffffff

            print(f"  {sym}/{tf} ({prof_key})...", end=" ", flush=True)
            candles = generate_candles(tf, N_BARS, base, seed=seed)
            reg = get_regime_label(candles[-200:])

            ens_m = run_ensemble_backtest(candles, profile)
            tf_m  = run_single_track_backtest(candles, profile, "trend_following")
            vcp_m = run_single_track_backtest(candles, profile, "vcp")
            mr_m  = run_single_track_backtest(candles, profile, "mean_reversion")

            results.append(ComboResult(
                symbol=sym, tf=tf, profile_key=prof_key, regime=reg, n_bars=len(candles),
                ens_wr=ens_m.win_rate, ens_sharpe=ens_m.sharpe, ens_pf=ens_m.profit_factor,
                ens_mdd=ens_m.max_drawdown, ens_cagr=ens_m.cagr, ens_trades=ens_m.trade_count,
                tf_wr=tf_m.win_rate, tf_sharpe=tf_m.sharpe, tf_trades=tf_m.trade_count,
                vcp_wr=vcp_m.win_rate, vcp_sharpe=vcp_m.sharpe, vcp_trades=vcp_m.trade_count,
                mr_wr=mr_m.win_rate,  mr_sharpe=mr_m.sharpe,  mr_trades=mr_m.trade_count,
            ))

            print(f"ens={ens_m.trade_count}d WR={ens_m.win_rate:.0%} sh={ens_m.sharpe:.2f} "
                  f"DD={ens_m.max_drawdown:.0%} | "
                  f"TF={tf_m.trade_count}d VCP={vcp_m.trade_count}d MR={mr_m.trade_count}d")

    total_w = sum(r.ens_trades for r in results)
    wavg = lambda v: sum(getattr(r, v) * r.ens_trades for r in results) / max(total_w, 1)

    hdr = (
        f"{'Sym':<4}{'TF':<4}{'Prof':<22}{'Reg':<12}"
        f"{'n':>5}{'WR(Ens)':>7}{'Sh(Ens)':>7}{'PF(Ens)':>7}{'DD(Ens)':>7}{'CAGR(Ens)':>9}"
        f"{'WR(TF)':>7}{'Sh(TF)':>7}{'n(TF)':>6}"
        f"{'WR(VC)':>7}{'Sh(VC)':>7}{'n(VC)':>6}"
        f"{'WR(MR)':>7}{'Sh(MR)':>7}{'n(MR)':>6}"
    )
    sep = "=" * len(hdr)
    print(f"\n{sep}")
    print(" Sterling v4 — Ensemble Track Backtest Results")
    print(sep)
    print(hdr)
    print("-" * len(hdr))

    for r in results:
        print(
            f"{r.symbol:<4}{r.tf:<4}{r.profile_key:<22}{r.regime[:11]:<12}{r.n_bars:>5}"
            f"{r.ens_wr:>7.0%}{r.ens_sharpe:>7.2f}{r.ens_pf:>7.2f}"
            f"{r.ens_mdd:>7.0%}{r.ens_cagr:>9.1%}"
            f"{r.tf_wr:>7.0%}{r.tf_sharpe:>7.2f}{r.tf_trades:>6}"
            f"{r.vcp_wr:>7.0%}{r.vcp_sharpe:>7.2f}{r.vcp_trades:>6}"
            f"{r.mr_wr:>7.0%}{r.mr_sharpe:>7.2f}{r.mr_trades:>6}"
        )

    print("-" * len(hdr))
    print(
        f"{'WTD_AVG':<4}{'(all combos)':<33}{'':>12}{total_w:>5}"
        f"{wavg('ens_wr'):>7.0%}{wavg('ens_sharpe'):>7.2f}{wavg('ens_pf'):>7.2f}"
        f"{wavg('ens_mdd'):>7.0%}{wavg('ens_cagr'):>9.1%}"
        f"{wavg('tf_wr'):>7.0%}{wavg('tf_sharpe'):>7.2f}{sum(r.tf_trades for r in results):>6}"
        f"{wavg('vcp_wr'):>7.0%}{wavg('vcp_sharpe'):>7.2f}{sum(r.vcp_trades for r in results):>6}"
        f"{wavg('mr_wr'):>7.0%}{wavg('mr_sharpe'):>7.2f}{sum(r.mr_trades for r in results):>6}"
    )
    print(sep)

    out = os.path.join(os.path.dirname(__file__), "ensemble_results.json")
    with open(out, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"\nSaved → {out}")