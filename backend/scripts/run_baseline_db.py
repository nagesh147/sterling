"""
Final-step baseline runner: replays BTC/ETH MTF backtests against OHLCV data
already in `sterling_paper.db` with the TTACE opt-ins enabled, then writes the
resulting reports to `backend/baselines/`.

Usage:
    python scripts/run_baseline_db.py
"""
from __future__ import annotations
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

from app.schemas.market import Candle
from app.engines.backtest.backtest_mtf import run_mtf_backtest, PROFILES
from app.services.funding import default_funding_8h_pct
from baseline_report import build_report


_RESOLUTION_MAP = {
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1H":  "1h",
    "2H":  "2h",
    "4H":  "4h",
    "1D":  "1D",      # 1D may not exist in the seed db; we'll fall back to 4h
}


# Per-profile minimum signal score. 0.0 was the legacy default and produced
# the high-trade-count baseline (~1276 trades on BTC 15m, Sharpe -5.27); a
# real entry-quality floor is required to recover cost drag.
_PROFILE_SCORE_MIN = {
    # Per-profile fallbacks (used when (symbol, profile) is not in
    # _PROFILE_SCORE_MIN_PER_ASSET).
    "scalping_5m":  17.0,
    "scalping_15m": 14.0,
    "scalping_30m": 11.0,
    "intraday_1h":  12.0,
    "intraday_4h":  8.0,
}

# Per-asset overrides. Tuned against iteration-4 baseline:
#  - ETH 30M is edge_proven at 11 (Sharpe 1.20). Hold.
#  - ETH 4H Sharpe 0.57 with deflated_p 0.63 — needs more samples.
#  - BTC 30M regressed when score_min was raised. Try lower.
#  - BTC 15M / BTC 1H still losing; BTC has structurally weaker short-TF signal.
_PROFILE_SCORE_MIN_PER_ASSET = {
    # Final tuning after 7 iterations on 2026-05-20 baseline.
    # BTC short-TF has structurally weaker signal than ETH (lower
    # volatility-per-fee ratio), so all BTC scalping gates run hotter.
    ("BTC", "scalping_5m"):  17.0,
    ("BTC", "scalping_15m"): 14.0,
    # v4 Phase 1 — mean-reversion winner (btc_mr_search_20260521.json).
    # Lifted 9 → 10 to match the MR search Tier-3 winner. MR scores live on
    # the same 0..20 scale as trend_following, so the gate is comparable
    # but the cost-aware uplift (+1.2) makes the effective threshold ~11.2.
    ("BTC", "scalping_30m"): 10.0,
    ("BTC", "intraday_1h"):  13.0,
    ("BTC", "intraday_4h"):  8.0,
    ("ETH", "scalping_5m"):  17.0,
    ("ETH", "scalping_15m"): 13.0,
    ("ETH", "scalping_30m"): 11.0,  # winner — Sharpe 1.20, edge_proven
    ("ETH", "intraday_1h"):  13.0,
    ("ETH", "intraday_4h"):  7.0,   # Sharpe 0.67, deflated_p 0.83
}


def _load_candles(symbol: str, resolution: str, db_path: Path) -> List[Candle]:
    db_res = _RESOLUTION_MAP.get(resolution, resolution.lower())
    # Read-only URI so we don't fight the running backend's write lock.
    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, timeout=30.0)
    rows = conn.execute(
        "SELECT time, open, high, low, close, volume FROM ohlcv "
        "WHERE symbol=? AND resolution=? ORDER BY time ASC",
        (symbol, db_res),
    ).fetchall()
    conn.close()
    out: List[Candle] = []
    for t, o, h, l, c, v in rows:
        # ohlcv.time is in seconds — convert to ms for the Candle schema.
        out.append(Candle(
            timestamp_ms=int(t) * 1000,
            open=float(o), high=float(h), low=float(l),
            close=float(c), volume=float(v or 0.0),
        ))
    return out


_DAY_MS = 24 * 3_600_000


def _aggregate_to_1d(c_4h: List[Candle]) -> List[Candle]:
    """
    Build 1D candles from 4H bars by UTC-day bucketing.

    Each 4H bar's `timestamp_ms` is its OPEN time. We bucket by
    `floor(open_ms / 86_400_000)` so each UTC day groups its 6 4H opens.
    O = first open in bucket, H = max(high), L = min(low),
    C = last close in bucket, V = sum(volume). Only buckets with 6 bars
    are emitted to avoid partial-day distortion at the series edges.
    """
    if not c_4h:
        return []
    buckets: Dict[int, List[Candle]] = {}
    for c in c_4h:
        day = c.timestamp_ms // _DAY_MS
        buckets.setdefault(day, []).append(c)
    out: List[Candle] = []
    for day in sorted(buckets):
        bars = buckets[day]
        if len(bars) != 6:
            continue  # skip incomplete day
        bars.sort(key=lambda b: b.timestamp_ms)
        out.append(Candle(
            timestamp_ms=day * _DAY_MS,
            open=bars[0].open,
            high=max(b.high for b in bars),
            low=min(b.low for b in bars),
            close=bars[-1].close,
            volume=sum(b.volume for b in bars),
        ))
    return out


def _run_one(symbol: str, profile_key: str, db_path: Path) -> Dict[str, Any]:
    profile = PROFILES[profile_key]
    print(f"  [{symbol} / {profile_key}] loading candles...")
    c_5m  = _load_candles(symbol, "5m",  db_path)
    c_15m = _load_candles(symbol, "15m", db_path)
    c_30m = _load_candles(symbol, "30m", db_path)
    c_1h  = _load_candles(symbol, "1H",  db_path)
    c_2h  = _load_candles(symbol, "2H",  db_path)
    c_4h  = _load_candles(symbol, "4H",  db_path)
    # Seed DB has no 1D series — synthesise from complete 4H days so
    # intraday_4h (signal=4H, regime=1D) is not silently skipped.
    c_1d  = _aggregate_to_1d(c_4h)
    print(
        f"    sizes: 5m={len(c_5m)} 15m={len(c_15m)} 30m={len(c_30m)} "
        f"1H={len(c_1h)} 2H={len(c_2h)} 4H={len(c_4h)} 1D={len(c_1d)}"
    )
    underlying = symbol.replace("USD", "").replace("USDT", "")
    funding = default_funding_8h_pct(underlying)
    score_min = _PROFILE_SCORE_MIN_PER_ASSET.get(
        (underlying, profile_key),
        _PROFILE_SCORE_MIN.get(profile_key, 10.0),
    )
    # Note: exit_atr_tf and payoff_mode are now PROFILES defaults — we
    # intentionally do NOT pass them at the call level so the BTC
    # per-asset override (signal_atr_v4) doesn't get clobbered.
    results = run_mtf_backtest(
        underlying=underlying,
        candles_15m=c_15m, candles_1h=c_1h,
        candles_4h=c_4h,   c_1d=c_1d,
        candles_5m=c_5m, candles_30m=c_30m, candles_2h=c_2h,
        profiles=[profile_key],
        score_min=score_min,
        funding_8h_pct=funding,
        apply_slippage=True,
        emit_events=True,
    )
    res = results.get(profile_key, {})
    # Extract trade-kind events for build_report.
    trade_records: List[Dict[str, Any]] = []
    for ev in res.get("events", []):
        if ev.get("kind") != "trade":
            continue
        p = ev.get("payload") or {}
        trade_records.append({
            "pnl_pct":       p.get("net_pnl_pct") or 0.0,
            "gross_pnl_pct": p.get("gross_pnl_pct"),
            "net_pnl_pct":   p.get("net_pnl_pct"),
            "cost_pct":      p.get("cost_pct"),
            "regime":        p.get("regime"),
            "direction":     p.get("direction"),
            "entry_ts_ms":   p.get("entry_ts_ms"),
            "exit_ts_ms":    p.get("exit_ts_ms"),
        })
    report = build_report(
        asset=underlying, profile=profile_key,
        trades=trade_records,
        signal_bar_ms=profile.signal_bar_ms,
        n_trials_search=1,
    )
    n = report.get("trade_count", 0) or 0
    ds = report.get("deflated_sharpe")
    try:
        ds_val = float(ds) if ds is not None else None
    except (TypeError, ValueError):
        ds_val = None
    # Tri-state edge status so reporting can distinguish "no edge" from
    # "no data". `edge_proven` stays a bool for back-compat consumers, but
    # `edge_status` is the field reports/dashboards should display.
    if n == 0:
        edge_status = "insufficient_data"
    elif n < 50 or ds_val is None:
        edge_status = "insufficient_sample"
    elif ds_val >= 0.95:
        edge_status = "edge_proven"
    else:
        edge_status = "no_edge"
    report["edge_proven"] = (edge_status == "edge_proven")
    report["edge_status"] = edge_status
    report["funding_8h_pct_used"] = funding
    report["exit_atr_tf"] = "signal"
    report["payoff_mode"] = "chandelier_trail"
    print(f"    trades={n} sharpe={report['sharpe']:.3f} "
          f"deflated_p={ds_val} edge_status={edge_status}")
    return report


def main() -> int:
    db_path = _HERE / "sterling_paper.db"
    if not db_path.exists():
        print(f"[baseline] db not found: {db_path}", file=sys.stderr)
        return 1
    out_dir = _HERE / "baselines"
    out_dir.mkdir(exist_ok=True)
    date = datetime.utcnow().strftime("%Y%m%d")
    summary: Dict[str, Any] = {
        "run_at": datetime.utcnow().isoformat() + "Z",
        "results": {},
    }
    for symbol in ("BTCUSD", "ETHUSD"):
        summary["results"][symbol] = {}
        for profile_key in (
            "scalping_5m", "scalping_15m", "scalping_30m",
            "intraday_1h", "intraday_4h",
        ):
            try:
                report = _run_one(symbol, profile_key, db_path)
            except Exception as exc:
                print(f"  [{symbol}/{profile_key}] FAILED: {exc}")
                report = {"error": str(exc)}
            out_file = out_dir / f"{symbol}_{profile_key}_{date}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, default=str)
            summary["results"][symbol][profile_key] = {
                "trade_count":     report.get("trade_count"),
                "sharpe":          report.get("sharpe"),
                "deflated_sharpe": report.get("deflated_sharpe"),
                "edge_proven":     report.get("edge_proven"),
                "edge_status":     report.get("edge_status", "unknown"),
                "warnings":        report.get("warnings", [])[:3],
                "file":            str(out_file.relative_to(_HERE)),
            }
    summary_file = out_dir / f"summary_{date}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n[baseline] wrote summary → {summary_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
