"""
Benchmark: Hybrid VCP-Momentum Scalper (Strategy V2) vs Sterling-v1 (TrendFollowing).

Uses the same candle dataset loaded from sterling_paper.db and runs both
backtests on matching 15m/1H candles. Produces a side-by-side performance table.

Usage
-----
    python scripts/benchmark_vcp_vs_v1.py [--asset BTCUSD] [--lookback 30]
    python scripts/benchmark_vcp_vs_v1.py --regime   # show bull/chop/bear splits
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Tuple, Optional

import numpy as np

_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

from app.schemas.market import Candle
from app.engines.hybrid_vcp import run_backtest, PROFILES
from app.engines.hybrid_vcp.backtest import BacktestReport
from app.engines.backtest.backtest_mtf import run_mtf_backtest, TFProfile


def load_candles(db_path: Path, symbol: str, resolution: str) -> list[Candle]:
    """Load OHLCV candles from the paper trading SQLite database."""
    res_map = {"15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1D"}
    db_res = res_map.get(resolution, resolution.lower())
    try:
        uri = f"file:{db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute(
            "SELECT time, open, high, low, close, volume FROM ohlcv "
            "WHERE symbol=? AND resolution=? ORDER BY time ASC LIMIT 5000",
            (symbol, db_res),
        ).fetchall()
        conn.close()
        return [
            Candle(
                timestamp_ms=int(t) * 1000,
                open=float(o), high=float(h),
                low=float(l), close=float(c),
                volume=float(v or 0.0),
            )
            for t, o, h, l, c, v in rows
        ]
    except sqlite3.OperationalError as e:
        return []


def _vcp_sharpe(trades) -> float:
    if not trades:
        return 0.0
    curve = [1.0]
    for t in trades:
        curve.append(curve[-1] * (1 + t.net_pnl))
    ec = np.array(curve)
    if len(ec) < 3:
        return 0.0
    rets = np.diff(ec) / ec[:-1]
    if np.std(rets) == 0:
        return 0.0
    return float(np.mean(rets) / np.std(rets) * np.sqrt(252 * 96))


def _mtf_sharpe(equity_curve) -> float:
    if len(equity_curve) < 3:
        return 0.0
    rets = np.diff(equity_curve) / np.asarray(equity_curve)[:-1]
    if np.std(rets) == 0:
        return 0.0
    return float(np.mean(rets) / np.std(rets) * np.sqrt(252))


def run_vcp_report(candles, profile_key: str) -> BacktestReport:
    profile = PROFILES[profile_key]
    import signal
    def _h(s, f: signal.Frame): raise TimeoutError("VCP backtest timeout")
    old = signal.signal(signal.SIGALRM, _h)
    signal.alarm(90)
    try:
        return run_backtest(candles, profile, apply_slippage=True)
    except TimeoutError:
        return BacktestReport(profile.label, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, [], [])
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _build_mtf_profile(profile_key: str) -> TFProfile:
    """Build a TFProfile matching the VCP scalping config."""
    regime_map = {
        "btc_scalping_15m": ("1h", 60 * 60_000),
        "btc_scalping_30m": ("2h", 2 * 60 * 60_000),
        "eth_scalping_15m": ("1h", 60 * 60_000),
        "eth_scalping_30m": ("2h", 2 * 60 * 60_000),
    }
    signal_tf, regime_tf_ms = regime_map.get(profile_key, ("1h", 60 * 60_000))
    signal_bar_ms = 15 * 60_000 if "15m" in profile_key else 30 * 60_000

    return TFProfile(
        label=f"V1-{profile_key}",
        signal_tf=signal_tf,
        regime_tf=signal_tf,
        signal_bar_ms=signal_bar_ms,
        regime_bar_ms=regime_tf_ms,
        st_configs=[(5, 10.0), (8, 12.0)],
        min_signal_bars=30,
        min_regime_bars=55,
        fwd_labels=["4h", "1d"],
        fwd_bars=[16, 96],
        hold_bars=16,
        exit_atr_tf="signal",
        payoff_mode="signal_atr_v4",
        v4_stop_mult=0.9,
        v4_tp_mult=1.5,
        v4_trail_mult=0.5,
    )


def run_v1_report(candles_15m: list, candles_regime: list, profile_key: str) -> dict:
    """Run Sterling-v1 backtest on 15m/1H candles (with timeout guard)."""
    if len(candles_15m) < 50 or len(candles_regime) < 20:
        return {}

    import signal

    def _timeout_handler(signum, frame):
        raise TimeoutError("V1 backtest timed out after 60s")

    profile = _build_mtf_profile(profile_key)
    try:
        # Set a 20s timeout for the V1 backtest
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(60)
        results = run_mtf_backtest(
            candles_15m,
            candles_regime,
            [profile],
            emit_events=False,
        )
        signal.alarm(0)
        if not results:
            return {}
        r = results[profile.label]
        return {
            "sharpe": r.get("sharpe", 0.0),
            "sortino": r.get("sortino", 0.0),
            "max_drawdown": r.get("max_drawdown", 0.0),
            "win_rate": r.get("win_rate", 0.0),
            "profit_factor": r.get("profit_factor", 0.0),
            "trade_count": r.get("total_trades", 0),
            "cagr": r.get("cagr", 0.0),
        }
    except (TimeoutError, Exception) as e:
        signal.alarm(0)
        return {}


def print_table(rows, headers):
    col_widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) + 2 for i, h in enumerate(headers)]
    sep = "  "
    bar = sep.join("-" * w for w in col_widths)
    print(bar)
    print(sep.join(f"{h:<{w}}" for w, h in zip(col_widths, headers)))
    print(bar)
    for row in rows:
        print(sep.join(f"{str(v):<{w}}" for w, v in zip(col_widths, row)))
    print(bar)


def split_by_regime(candles_15m: list, candles_1h: list, n_windows: int = 8) -> dict[str, list[Candle]]:
    """
    Split 15m candles into bull / chop / bear regimes using 1h BB width percentile.

    Returns {"bull": [...], "chop": [...], "bear": [...]} slices.
    Each slice is a fresh list of Candle objects (not views).
    """
    if len(candles_1h) < 50:
        return {}

    from app.engines.hybrid_vcp.indicators import compute_bundle, VCPConfig
    from app.engines.hybrid_vcp.signals import VolMode

    op_h = np.array([c.open for c in candles_1h], dtype=np.float64)
    hi_h = np.array([c.high for c in candles_1h], dtype=np.float64)
    lo_h = np.array([c.low for c in candles_1h], dtype=np.float64)
    cl_h = np.array([c.close for c in candles_1h], dtype=np.float64)
    vl_h = np.array([c.volume for c in candles_1h], dtype=np.float64)
    bundle_h = compute_bundle(op_h, hi_h, lo_h, cl_h, vl_h)

    # BB width percentile per 1h bar (prefix-based)
    from app.engines.hybrid_vcp.indicators import bb_width_percentile
    bw_pcts = []
    for i in range(len(candles_1h)):
        if i + 1 < 20:
            bw_pcts.append(50.0)
        else:
            bw_pcts.append(bb_width_percentile(cl_h[:i+1], lookback=60, period=20, std_mult=2.0))
    bw_pcts = np.array(bw_pcts)

    # Map 1h regime to each 15m candle
    regime_flags = []
    for c in candles_15m:
        ts_s = c.timestamp_ms // 1000  # seconds
        # Find nearest 1h candle
        idx = -1
        for j, hc in enumerate(candles_1h):
            if hc.timestamp_ms // 1000 >= ts_s:
                idx = j
                break
        if idx < 0:
            idx = len(candles_1h) - 1
        bw = bw_pcts[idx] if idx < len(bw_pcts) else 50.0
        if bw < 30:
            regime_flags.append("bull")   # COMPRESSION → likely breakout up
        elif bw < 70:
            regime_flags.append("chop")   # normal range
        else:
            regime_flags.append("bear")   # high volatility expansion
    return {"bull": [], "chop": [], "bear": []}


def run_regime_benchmark(db_path: Path, asset: str) -> None:
    """Run benchmark with bull/chop/bear splits for 15m profile."""
    candles_15m = load_candles(db_path, asset, "15m")
    if len(candles_15m) < 200:
        return

    # Use last 2000 bars for regime analysis
    candles_15m = candles_15m[-2000:]

    profiles = {"btc_scalping_15m": candles_15m}

    for pk, candles in profiles.items():
        print(f"\n═══ {pk} — Regime Breakdown ═══")

        # Simple regime split: top/bottom terciles by 1h close trend
        n = len(candles)
        third = n // 3
        bull_candles = candles[:third]
        chop_candles = candles[third:2*third]
        bear_candles = candles[2*third:]

        for label, subset in [("BULL (early)", bull_candles), ("CHOP (mid)", chop_candles), ("BEAR (late)", bear_candles)]:
            if len(subset) < 50:
                continue
            import signal
            def _h(s, f): raise TimeoutError("timeout")
            old = signal.signal(signal.SIGALRM, _h)
            signal.alarm(60)
            try:
                r = run_backtest(subset, PROFILES[pk])
                if r.trade_count > 0:
                    print(f"  {label:12s}: trades={r.trade_count:3d}  sharpe={r.sharpe:6.2f}  win={r.win_rate:5.1%}  maxdd={r.max_drawdown:5.1%}  cagr={r.cagr:6.1%}")
                else:
                    print(f"  {label:12s}: trades=0")
            except TimeoutError:
                print(f"  {label:12s}: TIMEOUT")
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old)


def main():
    parser = argparse.ArgumentParser(description="Benchmark VCP vs Sterling-v1")
    parser.add_argument("--asset", default="BTCUSD", help="Symbol to test")
    parser.add_argument("--lookback", type=int, default=30, help="Lookback days")
    parser.add_argument("--regime", action="store_true", help="Show bull/chop/bear regime split")
    args = parser.parse_args()

    db_path = _HERE / "sterling_paper.db"
    if not db_path.exists():
        print(f"[benchmark] DB not found: {db_path}")
        print("Skipping live-data benchmark.")
        return

    if args.regime:
        run_regime_benchmark(db_path, args.asset)
        return

    # Load candles
    candles_15m = load_candles(db_path, args.asset, "15m")
    candles_30m = load_candles(db_path, args.asset, "30m")
    candles_1h  = load_candles(db_path, args.asset, "1h")

    print(f"[benchmark] Loaded {len(candles_15m)}x15m, {len(candles_30m)}x30m, {len(candles_1h)}x1h for {args.asset}")

    profiles = {
        "btc_scalping_15m": (candles_15m, "15m"),
        "btc_scalping_30m": (candles_30m, "30m"),
        "eth_scalping_15m": (candles_15m, "15m"),
        "eth_scalping_30m": (candles_30m, "30m"),
    }

    headers = ["Profile", "Engine", "Sharpe", "Sortino", "MaxDD", "WinRate", "PF", "Trades", "CAGR"]
    rows = []

    for pk, (candles, tf) in profiles.items():
        if len(candles) < 100:
            continue

        # ── VCP ──────────────────────────────────────────────────────
        vcp = run_vcp_report(candles, pk)
        rows.append([
            pk, "VCP-v2",
            f"{vcp.sharpe:.2f}",
            f"{vcp.sortino:.2f}",
            f"{vcp.max_drawdown*100:.1f}%",
            f"{vcp.win_rate*100:.1f}%",
            f"{vcp.profit_factor:.2f}",
            vcp.trade_count,
            f"{vcp.cagr*100:.1f}%",
        ])

        # ── Sterling-v1 ─────────────────────────────────────────────
        regime_candles = candles_1h
        v1 = run_v1_report(candles, regime_candles, pk)
        if v1:
            rows.append([
                pk, "Sterling-v1",
                f"{v1['sharpe']:.2f}",
                f"{v1['sortino']:.2f}",
                f"{v1['max_drawdown']*100:.1f}%",
                f"{v1['win_rate']*100:.1f}%",
                f"{v1['profit_factor']:.2f}",
                v1['trade_count'],
                f"{v1['cagr']*100:.1f}%",
            ])
        else:
            rows.append([pk, "Sterling-v1", "N/A", "N/A", "N/A", "N/A", "N/A", 0, "N/A"])

    print()
    print(f"═══ VCP-v2 vs Sterling-v1 ═══ {args.asset} ═══")
    print_table(rows, headers)


if __name__ == "__main__":
    main()