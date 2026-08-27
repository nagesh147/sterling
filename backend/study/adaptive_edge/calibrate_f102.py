"""Fit F-102, the directional probability model, on real NIFTY bars.

This is the quantity the entry gate has been refusing on. §35 requires
ConservativeEV > 0, ConservativeEV is LowerConfidenceBound(EV), and a bound on
expected value needs a distribution over outcomes — which is F-102. Without it
the engine correctly declines every trade, so fitting it is the difference
between "cannot decide" and "decided not to".

Fitting it does not mean it works. A model can fit and have no edge, in which
case the conservative bound sits at or below zero and the gate stays shut for a
measured reason instead of a missing one. Both outcomes are reported.

Method, and why each part is there:

* **Causal features only.** Every feature at bar i uses bars <= i. The structure
  builder already enforces this; the labels are what could leak, so they are
  built forward from i+1 and never touch the feature window.
* **Purged, embargoed walk-forward folds.** A label spans `horizon` bars, so a
  row decided just before a fold boundary is still resolving after it. Training
  on it leaks the outcome the next segment is judged on. Purge and embargo are
  both set to the horizon for that reason, not tuned.
* **Out-of-sample only.** Every number reported comes from the holdout segment
  of each fold, which no fitting or temperature search touched.

Run:  python -m study.adaptive_edge.calibrate_f102
"""
from __future__ import annotations

import json
import math
import pathlib
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.engines.adaptive_edge.calibration import CalibrationConfig, fit_temperature
from app.engines.adaptive_edge.parameter_fitting import FittingConfig, fit_multinomial_logistic
from app.engines.adaptive_edge.canonical_math import multinomial_logistic
from app.engines.adaptive_edge.probability_engine import ModelParameters
from app.engines.adaptive_edge.walk_forward import build_folds

BARS_DB = pathlib.Path(__file__).resolve().parents[2] / "data" / "truedata_bars.sqlite"
OUT = pathlib.Path(__file__).resolve().parent / "out"

#: Bars ahead the label looks. A scalping horizon on a one-minute series.
HORIZON = 15
#: A move must clear this to count as directional rather than noise. Expressed
#: in basis points of spot so it means the same thing at any index level.
MOVE_BPS = 8.0
CLASS_NAMES = ("DOWN", "FLAT", "UP")


@dataclass(frozen=True)
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    oi: float


def load_bars(symbol: str = "NIFTY-I", interval: str = "1min") -> list[Bar]:
    con = sqlite3.connect(BARS_DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT provider_timestamp, open, high, low, close, volume, oi "
        "FROM truedata_bars WHERE symbol=? AND interval=? ORDER BY provider_timestamp",
        (symbol, interval),
    ).fetchall()
    con.close()
    out: list[Bar] = []
    for r in rows:
        try:
            out.append(Bar(
                ts=datetime.fromisoformat(str(r["provider_timestamp"])),
                open=float(r["open"] or 0), high=float(r["high"] or 0),
                low=float(r["low"] or 0), close=float(r["close"] or 0),
                volume=float(r["volume"] or 0), oi=float(r["oi"] or 0)))
        except (TypeError, ValueError):
            continue
    return [b for b in out if b.close > 0]


def _sma(values: Sequence[float], n: int) -> float:
    window = values[-n:]
    return sum(window) / len(window) if window else 0.0


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def build_rows(bars: list[Bar]) -> tuple[list[list[float]], list[int], list[datetime]]:
    """Causal features and forward labels.

    Features at i use bars[:i+1]. The label uses bars[i+1 : i+1+HORIZON] and is
    the only forward-looking quantity — which is what makes the purge and
    embargo below necessary rather than decorative.
    """
    features: list[list[float]] = []
    labels: list[int] = []
    stamps: list[datetime] = []
    warmup = 60

    closes = [b.close for b in bars]
    for i in range(warmup, len(bars) - HORIZON - 1):
        window = closes[max(0, i - warmup): i + 1]
        px = closes[i]
        rets = [(window[k] / window[k - 1] - 1.0) for k in range(1, len(window)) if window[k - 1] > 0]

        sma_fast, sma_slow = _sma(window, 5), _sma(window, 20)
        vol = _stdev(rets[-20:]) if len(rets) >= 2 else 0.0
        vols = [b.volume for b in bars[max(0, i - warmup): i + 1]]
        rel_vol = (vols[-1] / (sum(vols[:-1]) / max(1, len(vols) - 1))) - 1.0 if len(vols) > 1 and sum(vols[:-1]) > 0 else 0.0
        rng = (bars[i].high - bars[i].low) / px if px > 0 else 0.0
        body = (bars[i].close - bars[i].open) / px if px > 0 else 0.0
        oi_chg = 0.0
        if i > 0 and bars[i - 1].oi > 0:
            oi_chg = bars[i].oi / bars[i - 1].oi - 1.0

        features.append([
            (sma_fast / px - 1.0) * 100.0 if px > 0 else 0.0,
            (sma_slow / px - 1.0) * 100.0 if px > 0 else 0.0,
            vol * 100.0,
            max(-3.0, min(3.0, rel_vol)),
            rng * 100.0,
            body * 100.0,
            max(-3.0, min(3.0, oi_chg * 100.0)),
        ])

        forward = closes[i + 1: i + 1 + HORIZON]
        move_bps = ((forward[-1] / px) - 1.0) * 10_000.0 if px > 0 and forward else 0.0
        labels.append(2 if move_bps > MOVE_BPS else 0 if move_bps < -MOVE_BPS else 1)
        stamps.append(bars[i].ts)

    return features, labels, stamps


@dataclass
class _Row:
    """Minimal row so build_folds can order and slice these like research rows."""
    index: int
    decision_time: str


def main() -> int:
    bars = load_bars()
    print(f"bars loaded            : {len(bars):,}  {bars[0].ts:%Y-%m-%d} .. {bars[-1].ts:%Y-%m-%d}")
    features, labels, stamps = build_rows(bars)
    dist = {CLASS_NAMES[c]: labels.count(c) for c in (0, 1, 2)}
    print(f"rows                   : {len(features):,}")
    print(f"label distribution     : {dist}")
    base_rate = max(dist.values()) / len(labels)
    print(f"majority-class baseline: {base_rate:.4f}  <- anything at or below this has learned nothing")

    rows = [_Row(i, s.isoformat()) for i, s in enumerate(stamps)]
    # Absolute windows, not percentages: percentages of a 50k series give one
    # fold, and a single holdout is an anecdote rather than a walk-forward.
    train, val, hold = 8_000, 2_000, 2_000
    folds = build_folds(rows, train_size=train, validation_size=val, holdout_size=hold,
                        purge_rows=HORIZON, embargo_rows=HORIZON)
    print(f"walk-forward folds     : {len(folds)}  (purge={HORIZON}, embargo={HORIZON} = the label horizon)")
    if not folds:
        print("not enough rows for a single fold"); return 1

    results = []
    for k, fold in enumerate(folds, 1):
        tr = [r.index for r in fold.train]
        va = [r.index for r in fold.validation]
        ho = [r.index for r in fold.holdout]

        fit = fit_multinomial_logistic(
            features=[features[i] for i in tr], labels=[labels[i] for i in tr],
            class_names=CLASS_NAMES, config=FittingConfig(learning_rate=0.08, epochs=400),
            model_version=f"f102-fold{k}")
        params = fit.parameters

        def probs(i: int) -> list[float]:
            return multinomial_logistic(features[i], params.coefficients, params.intercepts)

        correct = sum(1 for i in ho if max(range(3), key=lambda c: probs(i)[c]) == labels[i])
        acc = correct / len(ho) if ho else 0.0

        # Directional edge: of the holdout rows the model called UP or DOWN with
        # conviction, how often was it right? That, not overall accuracy, is what
        # a trade would depend on.
        hits = calls = 0
        for i in ho:
            out = probs(i)
            top = max(range(3), key=lambda c: out[c])
            if CLASS_NAMES[top] == "FLAT" or out[top] < 0.40:
                continue
            calls += 1
            if top == labels[i]:
                hits += 1
        hit_rate = hits / calls if calls else 0.0
        results.append({"fold": k, "train": len(tr), "holdout": len(ho),
                        "accuracy": acc, "directional_calls": calls,
                        "directional_hit_rate": hit_rate,
                        "final_loss": fit.final_loss})
        print(f"  fold {k}: OOS acc {acc:.4f} | directional calls {calls:5d} "
              f"hit {hit_rate:.4f} | loss {fit.final_loss:.5f}")

    mean_acc = sum(r["accuracy"] for r in results) / len(results)
    total_calls = sum(r["directional_calls"] for r in results)
    mean_hit = (sum(r["directional_hit_rate"] * r["directional_calls"] for r in results) / total_calls) if total_calls else 0.0
    print(f"\nmean OOS accuracy      : {mean_acc:.4f}  (baseline {base_rate:.4f})")
    print(f"directional calls      : {total_calls:,}")
    print(f"directional hit rate   : {mean_hit:.4f}")
    verdict = ("EDGE" if mean_acc > base_rate + 0.01 and mean_hit > 0.40
               else "NO EDGE — the gate stays shut, now for a measured reason")
    print(f"verdict                : {verdict}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "F102_CALIBRATION.json").write_text(json.dumps({
        "symbol": "NIFTY-I", "interval": "1min", "bars": len(bars), "rows": len(features),
        "horizon_bars": HORIZON, "move_threshold_bps": MOVE_BPS,
        "label_distribution": dist, "majority_baseline": base_rate,
        "folds": results, "mean_oos_accuracy": mean_acc,
        "directional_calls": total_calls, "directional_hit_rate": mean_hit,
        "verdict": verdict,
    }, indent=2))
    print(f"written                : {OUT / 'F102_CALIBRATION.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
