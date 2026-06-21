"""Phase-0a: Deep-ITM depth sweep — find the optimal ITM depth for each index.

Uses the same replay harness as kite_st_sweep.py but sweeps ITM depth
(ITM5 → ITM20) with a fixed BS delta-approximated moneyness. The study
answers: "At what ITM depth does theta drag become negligible while premium
is still affordable?"

Run:  python -m study.kite_st_deep_itm
"""
from __future__ import annotations

import asyncio
import csv
import os
import warnings

import numpy as np

from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from study import kite_data
from study.kite_st_sweep import replay, OOS_FRAC, QTY, STARTING_CAPITAL

DTE_DAYS = 30.0
TRAIL_TARGET = "mid"  # the plan's validated default
DEPTHS = [
    ("ITM5",   5),
    ("ITM10", 10),
    ("ITM15", 15),
    ("ITM20", 20),
]
IV_VALUES = [0.14, 0.18, 0.22]

from app.services.kite_engine.backtest import OptionCosts


def run_deep_itm_sweep(data: dict) -> list:
    """Sweep ITM depth × IV for each index. Returns rows."""
    costs = OptionCosts()
    rows: list = []
    for name, arrs in data.items():
        median_spot = float(np.median(arrs["c"]))
        step = next(ix["strike_step"] for ix in kite_data.INDICES if ix["name"] == name)
        n = len(arrs["c"])
        oos_lo = int(n * (1 - OOS_FRAC))
        full = {k: arrs[k] for k in ("o", "h", "l", "c", "ts")}
        oos_seg = {k: arrs[k][oos_lo:n] for k in ("o", "h", "l", "c", "ts")}
        cfg = SterlingKiteEngineConfig(trail_target=TRAIL_TARGET)
        for depth_label, steps in DEPTHS:
            mny_pct = steps * step / median_spot * 100.0
            for iv in IV_VALUES:
                common = dict(cfg=cfg, trail_target=TRAIL_TARGET, early_lock=False,
                              profit_r=0.0, moneyness_pct=mny_pct, iv=iv,
                              dte_days=DTE_DAYS, qty=QTY, costs=costs,
                              starting_capital=STARTING_CAPITAL)
                sf, _ = replay(**full, **common)
                so, _ = replay(**oos_seg, **common)
                rows.append({
                    "underlying": name, "depth": depth_label, "steps": steps,
                    "iv": iv, "moneyness_pct": round(mny_pct, 3),
                    "full_ret": sf.return_pct, "full_pf": sf.profit_factor,
                    "full_sharpe": sf.sharpe, "full_trades": sf.trades,
                    "oos_ret": so.return_pct, "oos_pf": so.profit_factor,
                    "oos_trades": so.trades,
                })
    return rows


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    data = asyncio.run(kite_data.fetch_all())
    print(f"Deep-ITM sweep: {len(DEPTHS)} depths × {len(IV_VALUES)} IVs × {len(data)} indices")
    rows = run_deep_itm_sweep(data)
    out = os.path.join(os.path.dirname(__file__), "kite_st_deep_itm_results.csv")
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"{len(rows)} rows → {out}")

    # Summary: best OOS by index
    for name in sorted({r["underlying"] for r in rows}):
        subset = [r for r in rows if r["underlying"] == name]
        best = max(subset, key=lambda r: r["oos_ret"])
        print(f"  {name:<18} best={best['depth']} iv={best['iv']} "
              f"OOS={best['oos_ret']:.1f}%  PF={best['oos_pf']}")
