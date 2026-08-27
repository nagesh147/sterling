"""Fit F-102 on the specification's own order-flow features.

The first calibration used price/volume/OI derivatives and found no edge. That
result is only about those features. The Master Specification's directional
signal is order flow — §8 trade state, §9 aggressor state, §10 delta, §11
liquidity — which the bar table cannot express and the tick table can: it
carries ltp, bid, ask, bidqty and askqty.

So this run uses `structure.build_structure_series`, the engine's own feature
builder, over real bars and real ticks. Whatever it concludes is about the
strategy's features rather than about a proxy invented for a test.

The tick window is short — roughly nine sessions — so a negative result here is
weaker evidence than the 6.5-month bar run, and a positive one would need
confirming on more data before anyone traded it. Both caveats are reported.

Run:  python -m study.adaptive_edge.calibrate_f102_orderflow
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.engines.adaptive_edge.canonical_math import multinomial_logistic
from app.engines.adaptive_edge.parameter_fitting import FittingConfig, fit_multinomial_logistic
from app.engines.adaptive_edge.structure import build_structure_series
from app.engines.adaptive_edge.walk_forward import build_folds
from app.services.providers.truedata.adapter import TrueDataMarketDataAdapter

DATA = pathlib.Path(__file__).resolve().parents[2] / "data"
OUT = pathlib.Path(__file__).resolve().parent / "out"
HORIZON = 15
MOVE_BPS = 8.0
CLASS_NAMES = ("DOWN", "FLAT", "UP")


def _rows(db: str, table: str, cols: str) -> list[dict]:
    con = sqlite3.connect(DATA / db)
    con.row_factory = sqlite3.Row
    out = [dict(r) for r in con.execute(
        f"SELECT {cols} FROM {table} WHERE symbol='NIFTY-I' ORDER BY provider_timestamp")]
    con.close()
    return out


def main() -> int:
    bars_raw = _rows("truedata_bars.sqlite", "truedata_bars",
                     "provider_timestamp AS timestamp, open, high, low, close, volume, oi")
    ticks_raw = _rows("truedata_ticks.sqlite", "truedata_tick_quotes",
                      "provider_timestamp AS timestamp, ltp, volume, oi, bid, bidqty, ask, askqty")
    if not ticks_raw:
        print("no tick data"); return 1

    # Restrict bars to the tick window: order-flow features are only meaningful
    # where ticks exist, and padding with bar-only rows would dilute exactly the
    # signal this run is testing.
    first, last = ticks_raw[0]["timestamp"], ticks_raw[-1]["timestamp"]
    bars_raw = [b for b in bars_raw if first[:10] <= str(b["timestamp"])[:10] <= last[:10]]
    print(f"bars in tick window : {len(bars_raw):,}   ticks: {len(ticks_raw):,}")
    print(f"window              : {first[:10]} .. {last[:10]}")

    bar_events, tick_events = [], []
    for i, row in enumerate(bars_raw):
        try:
            bar_events.append(TrueDataMarketDataAdapter.create_bar_event("NIFTY-I", row, sequence=i))
        except (ValueError, TypeError):
            continue
    for i, row in enumerate(ticks_raw):
        try:
            tick_events.append(TrueDataMarketDataAdapter.create_tick_event("NIFTY-I", row, sequence=i))
        except (ValueError, TypeError):
            continue
    print(f"canonical events    : {len(bar_events):,} bars, {len(tick_events):,} ticks")

    series = build_structure_series(bar_events, tick_events, tick_size=0.05)
    print(f"structure snapshots : {len(series):,}")

    closes = [s.close for s in series]
    X, y = [], []
    warm = 30
    for i in range(warm, len(series) - HORIZON - 1):
        s = series[i]
        px = closes[i]
        if px <= 0:
            continue
        total = (s.buy_volume + s.sell_volume) or 1.0
        X.append([
            # §10 delta and §9 aggressor balance, normalized so magnitude does
            # not track session volume.
            s.bar_delta / total,
            (s.buy_volume - s.sell_volume) / total,
            s.cvd / max(abs(s.cvd) + total, 1.0),
            (px / s.vwap - 1.0) * 100.0 if s.vwap else 0.0,
            (px / s.poc - 1.0) * 100.0 if s.poc else 0.0,
            (s.vah - s.val) / px * 100.0 if s.vah and s.val else 0.0,
            1.0 if s.ib_complete else 0.0,
        ])
        fwd = closes[i + 1: i + 1 + HORIZON]
        bps = ((fwd[-1] / px) - 1.0) * 10_000.0 if fwd else 0.0
        y.append(2 if bps > MOVE_BPS else 0 if bps < -MOVE_BPS else 1)

    dist = {CLASS_NAMES[c]: y.count(c) for c in range(3)}
    base = max(dist.values()) / len(y) if y else 0.0
    print(f"rows                : {len(X):,}   labels {dist}   baseline {base:.4f}")
    if len(X) < 600:
        print("too few rows for a walk-forward"); return 1

    class R:
        def __init__(self, i): self.index = i
    rows = [R(i) for i in range(len(X))]
    train = max(200, int(len(X) * 0.35)); val = max(60, int(len(X) * 0.12)); hold = val
    folds = build_folds(rows, train_size=train, validation_size=val, holdout_size=hold,
                        purge_rows=HORIZON, embargo_rows=HORIZON)
    print(f"folds               : {len(folds)}")

    results, confident_total, confident_hits = [], 0, 0
    for k, fold in enumerate(folds, 1):
        tr = [r.index for r in fold.train]; ho = [r.index for r in fold.holdout]
        fit = fit_multinomial_logistic(features=[X[i] for i in tr], labels=[y[i] for i in tr],
                                       class_names=CLASS_NAMES,
                                       config=FittingConfig(learning_rate=0.08, epochs=400),
                                       model_version=f"of-fold{k}")
        p = fit.parameters
        pr = [multinomial_logistic(X[i], p.coefficients, p.intercepts) for i in ho]
        acc = sum(1 for j, i in enumerate(ho) if max(range(3), key=lambda c: pr[j][c]) == y[i]) / len(ho)
        calls = hits = 0
        for j, i in enumerate(ho):
            top = max(range(3), key=lambda c: pr[j][c])
            if CLASS_NAMES[top] == "FLAT" or pr[j][top] < 0.40:
                continue
            calls += 1; hits += 1 if top == y[i] else 0
        confident_total += calls; confident_hits += hits
        maxconf = max(max(row) for row in pr)
        results.append({"fold": k, "accuracy": acc, "calls": calls,
                        "hit_rate": hits / calls if calls else 0.0,
                        "max_confidence": maxconf, "final_loss": fit.final_loss})
        print(f"  fold {k}: OOS acc {acc:.4f} | calls {calls:4d} hit "
              f"{(hits/calls if calls else 0):.4f} | maxP {maxconf:.4f}")

    mean_acc = sum(r["accuracy"] for r in results) / len(results)
    hit = confident_hits / confident_total if confident_total else 0.0
    print(f"\nmean OOS accuracy   : {mean_acc:.4f}  (baseline {base:.4f})")
    print(f"directional calls   : {confident_total}   hit rate {hit:.4f}")
    verdict = ("EDGE" if mean_acc > base + 0.01 and confident_total > 30 and hit > 0.40
               else "NO EDGE on the specification's own order-flow features")
    print(f"verdict             : {verdict}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "F102_ORDERFLOW.json").write_text(json.dumps({
        "features": "specification order flow via structure.build_structure_series",
        "window": f"{first[:10]}..{last[:10]}", "bars": len(bar_events), "ticks": len(tick_events),
        "rows": len(X), "labels": dist, "baseline": base, "folds": results,
        "mean_oos_accuracy": mean_acc, "directional_calls": confident_total,
        "directional_hit_rate": hit, "verdict": verdict,
        "caveat": "roughly nine sessions of ticks; weaker evidence than the 6.5-month bar run",
    }, indent=2))
    print(f"written             : {OUT / 'F102_ORDERFLOW.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
