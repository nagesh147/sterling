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
    "15m": "15m",
    "1H":  "1h",
    "4H":  "4h",
    "1D":  "1D",      # 1D may not exist in the seed db; we'll fall back to 4h
}


def _load_candles(symbol: str, resolution: str, db_path: Path) -> List[Candle]:
    db_res = _RESOLUTION_MAP.get(resolution, resolution.lower())
    conn = sqlite3.connect(str(db_path))
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


def _run_one(symbol: str, profile_key: str, db_path: Path) -> Dict[str, Any]:
    profile = PROFILES[profile_key]
    print(f"  [{symbol} / {profile_key}] loading candles...")
    c_15m = _load_candles(symbol, "15m", db_path)
    c_1h  = _load_candles(symbol, "1H",  db_path)
    c_4h  = _load_candles(symbol, "4H",  db_path)
    c_1d: List[Candle] = []  # not stored in the seed DB
    print(f"    sizes: 15m={len(c_15m)} 1H={len(c_1h)} 4H={len(c_4h)}")
    underlying = symbol.replace("USD", "").replace("USDT", "")
    funding = default_funding_8h_pct(underlying)
    results = run_mtf_backtest(
        underlying=underlying,
        candles_15m=c_15m, candles_1h=c_1h,
        candles_4h=c_4h,   c_1d=c_1d,
        profiles=[profile_key],
        funding_8h_pct=funding,
        apply_slippage=True,
        emit_events=True,
        exit_atr_tf="signal",
        payoff_mode="chandelier_trail",
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
    report["edge_proven"] = (n >= 50 and (ds_val is not None) and ds_val >= 0.95)
    report["funding_8h_pct_used"] = funding
    report["exit_atr_tf"] = "signal"
    report["payoff_mode"] = "chandelier_trail"
    print(f"    trades={n} sharpe={report['sharpe']:.3f} "
          f"deflated_p={ds_val} edge_proven={report['edge_proven']}")
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
        for profile_key in ("scalping_15m", "intraday_1h", "intraday_4h"):
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
