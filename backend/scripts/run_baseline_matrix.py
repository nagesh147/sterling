"""
Baseline comparison matrix runner.

Sweeps BTC/ETH × {scalping_15m, intraday_1h, intraday_4h} × cost-config
permutations and writes one table row per cell to
`backend/baselines/matrix_<date>.json` (machine-readable) and
`backend/baselines/matrix_<date>.md` (human-readable).

The matrix isolates cost-component impact so we can answer:

  * Is the strategy losing BEFORE costs or only AFTER costs?
    → compare net at apply_slippage=False / funding_8h=0 vs observed.
  * Which cost dominates (slippage, fee, funding, option spread)?
    → row-over-row deltas.
  * Which exit/payoff combo is least bad?
    → exit_atr_tf × payoff_mode quadrants.

The cost components verified by `backend/app/engines/backtest/costs.py`:

    total_cost_pct = slippage_pct + fee_pct + funding_pct + option_spread_pct
    net_pnl_pct    = gross_pnl_pct - total_cost_pct

`gross_pnl_pct` is computed from CLEAN entry/exit prices — slippage is
attributed once as a cost component, never double-counted via effective
prices (see `compute_trade_costs` docstring).
"""
from __future__ import annotations
import json
import sqlite3
import sys
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any, Dict, List

_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

from app.schemas.market import Candle
from app.engines.backtest.backtest_mtf import run_mtf_backtest, PROFILES
from app.services.funding import default_funding_8h_pct
from baseline_report import build_report

# Inline copies of the loader helpers (scripts/ isn't a package, so we
# can't import from `scripts.run_baseline_db`). Keep them aligned with
# run_baseline_db.py — they're shared between both runners.
_RESOLUTION_MAP = {"15m": "15m", "1H": "1h", "4H": "4h", "1D": "1D"}
_DAY_MS = 24 * 3_600_000


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
    return [
        Candle(timestamp_ms=int(t) * 1000, open=float(o), high=float(h),
               low=float(l), close=float(c), volume=float(v or 0.0))
        for t, o, h, l, c, v in rows
    ]


def _aggregate_to_1d(c_4h: List[Candle]) -> List[Candle]:
    if not c_4h:
        return []
    buckets: Dict[int, List[Candle]] = {}
    for c in c_4h:
        buckets.setdefault(c.timestamp_ms // _DAY_MS, []).append(c)
    out: List[Candle] = []
    for day in sorted(buckets):
        bars = buckets[day]
        if len(bars) != 6:
            continue
        bars.sort(key=lambda b: b.timestamp_ms)
        out.append(Candle(
            timestamp_ms=day * _DAY_MS, open=bars[0].open,
            high=max(b.high for b in bars), low=min(b.low for b in bars),
            close=bars[-1].close, volume=sum(b.volume for b in bars),
        ))
    return out


SYMBOLS    = ("BTCUSD", "ETHUSD")
PROFILE_KEYS = ("scalping_15m", "intraday_1h", "intraday_4h")

# Cost-component knobs (full 2×2×2×2 = 16 combos per asset×profile).
APPLY_SLIPPAGE_OPTS = (False, True)
FUNDING_OPTS        = ("zero", "observed")
PAYOFF_OPTS         = ("chandelier_trail", "signal_atr_v4")
EXIT_ATR_OPTS       = ("regime", "signal")


def _edge_status(n: int, ds_val: float | None) -> str:
    if n == 0:
        return "insufficient_data"
    if n < 50 or ds_val is None:
        return "insufficient_sample"
    if ds_val >= 0.95:
        return "edge_proven"
    return "no_edge"


def _row(
    symbol: str, profile_key: str, candles: Dict[str, List[Candle]],
    *, apply_slippage: bool, funding_mode: str,
    payoff: str, exit_atr: str,
) -> Dict[str, Any]:
    underlying = symbol.replace("USD", "").replace("USDT", "")
    funding = default_funding_8h_pct(underlying) if funding_mode == "observed" else 0.0
    results = run_mtf_backtest(
        underlying=underlying,
        candles_15m=candles["15m"], candles_1h=candles["1h"],
        candles_4h=candles["4h"],   c_1d=candles["1d"],
        profiles=[profile_key],
        funding_8h_pct=funding,
        apply_slippage=apply_slippage,
        emit_events=True,
        exit_atr_tf=exit_atr,
        payoff_mode=payoff,
    )
    res = results.get(profile_key, {})
    trades: List[Dict[str, Any]] = []
    for ev in res.get("events", []):
        if ev.get("kind") != "trade":
            continue
        p = ev.get("payload") or {}
        trades.append({
            "pnl_pct":       p.get("net_pnl_pct") or 0.0,
            "gross_pnl_pct": p.get("gross_pnl_pct"),
            "net_pnl_pct":   p.get("net_pnl_pct"),
            "cost_pct":      p.get("cost_pct"),
            "regime":        p.get("regime"),
            "direction":     p.get("direction"),
            "entry_ts_ms":   p.get("entry_ts_ms"),
            "exit_ts_ms":    p.get("exit_ts_ms"),
        })
    profile = PROFILES[profile_key]
    report = build_report(
        asset=underlying, profile=profile_key,
        trades=trades, signal_bar_ms=profile.signal_bar_ms,
        n_trials_search=1,
    )
    n = int(report.get("trade_count") or 0)
    ds = report.get("deflated_sharpe")
    ds_val = float(ds) if ds is not None else None
    return {
        "asset":          underlying,
        "profile":        profile_key,
        "config": {
            "apply_slippage": apply_slippage,
            "funding_mode":   funding_mode,
            "funding_8h_pct": funding,
            "payoff":         payoff,
            "exit_atr_tf":    exit_atr,
        },
        "n_trades":       n,
        "gross_sum":      report.get("gross_pnl_sum"),
        "cost_sum":       report.get("cost_drag_sum"),
        "net_sum":        report.get("net_pnl_sum"),
        "sharpe":         report.get("sharpe"),
        "profit_factor":  report.get("profit_factor"),
        "deflated_sharpe": ds_val,
        "edge_status":    _edge_status(n, ds_val),
    }


def _load_all(symbol: str, db_path: Path) -> Dict[str, List[Candle]]:
    c_15m = _load_candles(symbol, "15m", db_path)
    c_1h  = _load_candles(symbol, "1H",  db_path)
    c_4h  = _load_candles(symbol, "4H",  db_path)
    c_1d  = _aggregate_to_1d(c_4h)
    return {"15m": c_15m, "1h": c_1h, "4h": c_4h, "1d": c_1d}


def _fmt_md(rows: List[Dict[str, Any]]) -> str:
    headers = [
        "asset", "profile", "slip", "funding", "payoff", "exit_atr",
        "n_trades", "gross_sum", "cost_sum", "net_sum",
        "sharpe", "PF", "DSR", "edge_status",
    ]
    out: List[str] = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    def _f(v, w=4):
        if v is None:
            return "—"
        if isinstance(v, float):
            return f"{v:.{w}f}"
        return str(v)
    for r in rows:
        c = r["config"]
        out.append("| " + " | ".join([
            r["asset"], r["profile"],
            "Y" if c["apply_slippage"] else "N",
            c["funding_mode"], c["payoff"], c["exit_atr_tf"],
            str(r["n_trades"]),
            _f(r["gross_sum"]), _f(r["cost_sum"]), _f(r["net_sum"]),
            _f(r["sharpe"], 3),
            _f(r["profit_factor"], 3),
            _f(r["deflated_sharpe"], 3),
            r["edge_status"],
        ]) + " |")
    return "\n".join(out) + "\n"


def main() -> int:
    db_path = _HERE / "sterling_paper.db"
    if not db_path.exists():
        print(f"[matrix] db not found: {db_path}", file=sys.stderr)
        return 1

    rows: List[Dict[str, Any]] = []
    for symbol in SYMBOLS:
        print(f"[{symbol}] loading candles…")
        candles = _load_all(symbol, db_path)
        print(f"  sizes: 15m={len(candles['15m'])} 1H={len(candles['1h'])} "
              f"4H={len(candles['4h'])} 1D={len(candles['1d'])}")
        for profile_key, slip, fund, pay, ex in product(
            PROFILE_KEYS, APPLY_SLIPPAGE_OPTS, FUNDING_OPTS,
            PAYOFF_OPTS, EXIT_ATR_OPTS,
        ):
            try:
                row = _row(symbol, profile_key, candles,
                           apply_slippage=slip, funding_mode=fund,
                           payoff=pay, exit_atr=ex)
            except Exception as exc:
                row = {
                    "asset": symbol.replace("USD",""), "profile": profile_key,
                    "config": {"apply_slippage": slip, "funding_mode": fund,
                               "payoff": pay, "exit_atr_tf": ex},
                    "error": str(exc),
                }
            rows.append(row)
            n = row.get("n_trades", 0)
            es = row.get("edge_status", row.get("error", "err"))
            sh = row.get("sharpe")
            sh_s = f"{sh:.3f}" if isinstance(sh, (int, float)) else "—"
            print(f"  {symbol}/{profile_key:<13} slip={int(slip)} "
                  f"fund={fund:<8} pay={pay:<17} ex={ex:<6} "
                  f"n={n:<4} sharpe={sh_s} {es}")

    out_dir = _HERE / "baselines"
    out_dir.mkdir(exist_ok=True)
    date = datetime.utcnow().strftime("%Y%m%d")
    json_path = out_dir / f"matrix_{date}.json"
    md_path   = out_dir / f"matrix_{date}.md"
    payload = {"run_at": datetime.utcnow().isoformat() + "Z", "rows": rows}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_fmt_md(rows))
    print(f"\n[matrix] wrote {json_path}")
    print(f"[matrix] wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
