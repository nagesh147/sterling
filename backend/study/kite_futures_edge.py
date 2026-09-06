"""Does the engine's own entry/exit logic make money on REAL executable futures?

Release gate P0-5 asks for expectancy measured on contracts an order can actually
be placed against. Cash and index bars cannot answer it, and option history does
not exist to answer it with (Kite refuses history for an expired contract, so it
can only be accumulated forward). Continuous DAILY futures is the one executable
series that goes back years, so this is the gate's futures half.

What is deliberately reused rather than reimplemented
-----------------------------------------------------
``replay_premium_series`` drives the engine's own ``compute_regime``,
``entry_transitions`` and ``exits`` — the same code the live scanner runs. It
enters at the next observed raw open, fills a breached stop no better than the
opening gap, and refuses to mark a series-end exit as executable. A separate
"backtest" written for this study would measure the study, not the engine.

Predeclared BEFORE the first run, so the criterion cannot be moved afterwards
-----------------------------------------------------------------------------
1. Split at ``HOLDOUT_FROM``. Everything from that date is untouched holdout.
2. PASS requires, on the holdout and after costs:
     a. aggregate net PnL > 0, AND
     b. median per-symbol net PnL > 0 — one lucky name is not an edge, AND
     c. (a) and (b) hold at every slippage in ``SLIPPAGE_GRID``.
3. Anything else is a FAIL. A result that only survives the lowest slippage is a
   FAIL, and is reported as one.

The parameters (21,1), (14,2), (7,3) were selected on index/spot hourly data
elsewhere in this repo, never on daily futures. Nothing here fits a parameter, so
the whole span is out-of-sample for them; the holdout split is the stricter,
second line of defence.

Long-only. ``replay_premium_series`` takes long entries only, and it is the
audited path; the short side of the futures vehicle is NOT measured here and must
not be inferred from these numbers.

    python study/kite_futures_edge.py --lake <path> --out report.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
from typing import Any, Dict, List

import pyarrow.parquet as pq

from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.services.kite_engine.backtest import FuturesCosts, replay_premium_series

DEFAULT_LAKE = Path("/run/media/nageshmadaram/3f36ac07-fdbe-48c1-9514-ecf65c6619b0/SterlingLake")

#: Untouched holdout. Chosen as a round two-year tail before any result was seen.
HOLDOUT_FROM = "2025-01-01"

#: The one cost input that is an assumption rather than a published rate.
SLIPPAGE_GRID = (0.0001, 0.0002, 0.0005)

#: Below this a symbol cannot support the warmup plus a meaningful number of
#: trades, and its "expectancy" would be noise quoted to two decimals.
MIN_BARS = 400


def _load(path: Path) -> Dict[str, Any] | None:
    table = pq.read_table(path)
    meta = {k.decode(): v.decode() for k, v in (table.schema.metadata or {}).items()}
    scale = float(meta.get("price_scale") or 1)
    if table.num_rows < MIN_BARS or scale <= 0:
        return None
    cols = table.to_pydict()
    return {
        "symbol": meta.get("tradingsymbol", path.stem),
        "ts_ms": [int(t.timestamp() * 1000) for t in cols["ts"]],
        "open": [v / scale for v in cols["open"]],
        "high": [v / scale for v in cols["high"]],
        "low": [v / scale for v in cols["low"]],
        "close": [v / scale for v in cols["close"]],
    }


def _split_index(ts_ms: List[int], iso: str) -> int:
    from datetime import datetime, timezone
    cut = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp() * 1000
    for i, t in enumerate(ts_ms):
        if t >= cut:
            return i
    return len(ts_ms)


def _run_one(series: Dict[str, Any], cfg, costs, qty: int,
             capital: float) -> Dict[str, Any] | None:
    try:
        run = replay_premium_series(
            timestamps_ms=series["ts_ms"], premium_open=series["open"],
            premium_high=series["high"], premium_low=series["low"],
            premium_close=series["close"], cfg=cfg, trail_target=cfg.trail_target,
            exit_mode=cfg.exit_mode, qty=qty, costs=costs,
            starting_capital=capital, direction_label="long")
    except ValueError:
        return None   # rejected OHLC — never silently repaired
    trades = [t for t in run.trades
              if not t.exit_reason.startswith("series-end")]
    if not trades:
        return None
    net = sum(t.net_pnl for t in trades)
    return {
        "symbol": series["symbol"], "trades": len(trades),
        "net_pnl": round(net, 2),
        "gross_pnl": round(sum(t.gross_pnl for t in trades), 2),
        "costs": round(sum(t.costs for t in trades), 2),
        "wins": sum(1 for t in trades if t.net_pnl > 0),
        "win_rate": round(sum(1 for t in trades if t.net_pnl > 0) / len(trades), 4),
    }


def audit(lake: Path, *, qty: int, capital: float) -> Dict[str, Any]:
    files = sorted((lake / "bars" / "interval=day").rglob("*.parquet"))
    futures = [p for p in files if "NFO-FUT" in str(p) or "BFO-FUT" in str(p)]
    cfg = SterlingKiteEngineConfig()
    loaded = [s for s in (_load(p) for p in futures) if s]

    by_slippage: Dict[str, Any] = {}
    for slip in SLIPPAGE_GRID:
        costs = FuturesCosts(slippage_pct=slip)
        windows: Dict[str, List[Dict[str, Any]]] = {"full": [], "holdout": []}
        for series in loaded:
            full = _run_one(series, cfg, costs, qty, capital)
            if full:
                windows["full"].append(full)
            cut = _split_index(series["ts_ms"], HOLDOUT_FROM)
            if len(series["ts_ms"]) - cut >= MIN_BARS // 2:
                tail = {k: (v[cut:] if isinstance(v, list) else v)
                        for k, v in series.items()}
                out = _run_one(tail, cfg, costs, qty, capital)
                if out:
                    windows["holdout"].append(out)
        summary = {}
        for name, rows in windows.items():
            nets = [r["net_pnl"] for r in rows]
            summary[name] = {
                "symbols": len(rows),
                "trades": sum(r["trades"] for r in rows),
                "aggregate_net_pnl": round(sum(nets), 2),
                "aggregate_gross_pnl": round(sum(r["gross_pnl"] for r in rows), 2),
                "aggregate_costs": round(sum(r["costs"] for r in rows), 2),
                "median_symbol_net_pnl": round(statistics.median(nets), 2) if nets else 0.0,
                "profitable_symbols": sum(1 for v in nets if v > 0),
                "worst_symbol_net_pnl": round(min(nets), 2) if nets else 0.0,
                "best_symbol_net_pnl": round(max(nets), 2) if nets else 0.0,
            }
        by_slippage[f"{slip}"] = summary

    holdouts = [by_slippage[f"{s}"]["holdout"] for s in SLIPPAGE_GRID]
    passed = bool(holdouts) and all(
        h["symbols"] > 0 and h["aggregate_net_pnl"] > 0 and h["median_symbol_net_pnl"] > 0
        for h in holdouts)
    return {
        "lake": str(lake),
        "criterion": {
            "holdout_from": HOLDOUT_FROM, "slippage_grid": list(SLIPPAGE_GRID),
            "requires": "holdout aggregate net > 0 AND median per-symbol net > 0, "
                        "at every slippage in the grid",
            "predeclared": True,
        },
        "vehicle": "NFO/BFO futures, continuous daily, long-only",
        "engine_logic": "app.services.kite_engine.backtest.replay_premium_series "
                        "(compute_regime + entry_transitions + exits, next-open entry, "
                        "gap-aware stops)",
        "position": {"qty": qty, "starting_capital": capital},
        "symbols_considered": len(futures),
        "symbols_with_enough_bars": len(loaded),
        "results_by_slippage": by_slippage,
        "verdict": "PASS" if passed else "FAIL",
        "caveats": [
            "Long-only. The short side of the futures vehicle is not measured.",
            "Daily bars. The live engine also runs intraday, which this cannot speak to.",
            "Continuous series are back-adjusted by the broker; roll costs are not "
            "separately modelled.",
            "One fixed quantity per trade, no position sizing and no portfolio risk.",
            "Slippage is an assumption swept across a grid, not an observed fill cost.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", type=Path, default=DEFAULT_LAKE)
    parser.add_argument("--qty", type=int, default=1)
    parser.add_argument("--capital", type=float, default=1_000_000.0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = audit(args.lake, qty=args.qty, capital=args.capital)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n")
    head = {"verdict": report["verdict"],
            "symbols": report["symbols_with_enough_bars"],
            "holdout": {s: report["results_by_slippage"][s]["holdout"]
                        for s in report["results_by_slippage"]}}
    print(json.dumps(head, indent=2))


if __name__ == "__main__":
    main()
