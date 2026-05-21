"""
Sterling v4 Phase 3 — BTC ML model training driver.

For each BTC scalping profile, train one short-side and one long-side
xgboost classifier via walk-forward + deflated-Sharpe gating, then persist
via `services/model_store.py`.

The persisted models are loaded at runtime by `tracks/ml_ensemble.py` when
the (asset, profile) is routed to "ml_ensemble" via the track_selector.
The router's YAML is NOT edited by this script — it's a deliberate manual
step so unintended ML routing requires an operator's explicit blessing.

Output:
  backend/models/<asset>_<profile_key>.xgb       # Booster binary
  backend/models/<asset>_<profile_key>.meta.json # ModelMeta
  backend/baselines/btc_ml_train_<YYYYMMDD>.json # per-profile train report
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

from app.schemas.market import Candle
from app.engines.ml.feature_library import build_feature_matrix, FEATURE_NAMES
from app.engines.ml.walk_forward_train import (
    train_walk_forward, WalkForwardTrainConfig,
)
from app.services.model_store import save_model, ModelMeta
from scripts.btc_scalping_search import _load_candles, _aggregate_to_1d


# Per-profile training config.
# expected_cost_pct matches TFProfile.expected_cost_bps / 10000.
# hold_bars matches TFProfile.hold_bars.
_TRAIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "scalping_5m":  {"sig_res": "5m",  "reg_res": "15m", "reg_bar_ms": 15 * 60_000,
                     "hold_bars": 16, "expected_cost_pct": 0.010},
    "scalping_15m": {"sig_res": "15m", "reg_res": "1H",  "reg_bar_ms": 60 * 60_000,
                     "hold_bars": 16, "expected_cost_pct": 0.008},
    "scalping_30m": {"sig_res": "30m", "reg_res": "2H",  "reg_bar_ms": 2 * 60 * 60_000,
                     "hold_bars": 10, "expected_cost_pct": 0.006},
}


def _train_one(
    asset: str, profile_key: str, direction_hint: int,
    candles_sig: List[Candle], candles_reg: List[Candle],
    reg_bar_ms: int, hold_bars: int, expected_cost_pct: float,
) -> Dict[str, Any]:
    print(f"\n┌── {asset} {profile_key} dir={'+1' if direction_hint==1 else '-1'} ─────")
    print(f"│ candles: signal={len(candles_sig)} regime={len(candles_reg)}")
    print(f"│ hold_bars={hold_bars} expected_cost_pct={expected_cost_pct}")
    t0 = time.time()
    X, ts = build_feature_matrix(candles_sig, candles_reg, regime_bar_ms=reg_bar_ms)
    print(f"│ feature matrix {X.shape} built in {time.time()-t0:.1f}s")
    close = np.array([c.close for c in candles_sig], dtype=np.float64)

    cfg = WalkForwardTrainConfig(
        n_splits=3, train_pct=0.7,
        min_train_bars=1000, min_pos_samples=100,
        hold_bars=hold_bars,
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, early_stopping=30,
    )
    t0 = time.time()
    res = train_walk_forward(
        X=X, feature_names=FEATURE_NAMES, close=close,
        direction_hint=direction_hint,
        expected_cost_pct=expected_cost_pct, config=cfg,
    )
    print(f"│ trained in {time.time()-t0:.1f}s")
    print(f"│ OOS Sharpe={res.oos_sharpe:.3f}  deflated_p={res.deflated_sharpe}")
    print(f"│ fold sharpes: {[round(f.test_sharpe, 3) for f in res.fold_metrics]}")
    print(f"│ top features: {sorted(res.feature_importance.items(), key=lambda kv: kv[1], reverse=True)[:5]}")
    print(f"│ stable features: {res.stable_features[:8]}")

    if res.best_model is None:
        print(f"│ NO MODEL — too few positive samples to fit final booster.")
        print(f"└──────────────────────────────────────────────────────────────")
        return {
            "asset": asset, "profile_key": profile_key,
            "direction_hint": direction_hint,
            "error": "no_final_model",
            "oos_sharpe": res.oos_sharpe,
            "deflated_sharpe": res.deflated_sharpe,
        }

    meta = ModelMeta(
        asset=asset, profile_key=profile_key,
        direction_hint=direction_hint,
        feature_names=list(FEATURE_NAMES),
        n_train_bars=int(X.shape[0]),
        oos_sharpe=float(res.oos_sharpe),
        deflated_sharpe=res.deflated_sharpe,
        fold_test_sharpes=[float(f.test_sharpe) for f in res.fold_metrics],
        feature_importance={k: float(v) for k, v in res.feature_importance.items()},
        stable_features=list(res.stable_features),
        trained_at=datetime.utcnow().isoformat() + "Z",
        profitable_mult=cfg.profitable_mult,
        hold_bars=hold_bars,
        expected_cost_pct=expected_cost_pct,
        notes=f"BTC ML ensemble; n_folds={len(res.fold_metrics)}",
    )

    # Per-asset naming includes the direction so long- and short-side models
    # coexist on disk. The track loader knows to pick by direction_hint.
    suffix = "_long" if direction_hint == 1 else "_short"
    meta_with_suffix = ModelMeta(
        asset=meta.asset,
        profile_key=meta.profile_key + suffix,
        direction_hint=meta.direction_hint,
        feature_names=meta.feature_names,
        n_train_bars=meta.n_train_bars,
        oos_sharpe=meta.oos_sharpe,
        deflated_sharpe=meta.deflated_sharpe,
        fold_test_sharpes=meta.fold_test_sharpes,
        feature_importance=meta.feature_importance,
        stable_features=meta.stable_features,
        trained_at=meta.trained_at,
        profitable_mult=meta.profitable_mult,
        hold_bars=meta.hold_bars,
        expected_cost_pct=meta.expected_cost_pct,
        notes=meta.notes,
    )
    model_path, meta_path = save_model(res.best_model, meta_with_suffix)
    print(f"│ saved → {model_path.name}")
    print(f"└──────────────────────────────────────────────────────────────")
    return {
        "asset": asset, "profile_key": profile_key,
        "direction_hint": direction_hint,
        "oos_sharpe": res.oos_sharpe,
        "deflated_sharpe": res.deflated_sharpe,
        "fold_test_sharpes": [float(f.test_sharpe) for f in res.fold_metrics],
        "stable_features":   res.stable_features,
        "top_features":      sorted(res.feature_importance.items(),
                                    key=lambda kv: kv[1], reverse=True)[:10],
        "model_path":        str(model_path),
        "meta_path":         str(meta_path),
    }


def main() -> int:
    db = _HERE / "sterling_paper.db"
    if not db.exists():
        print(f"[ml-train] db not found: {db}", file=sys.stderr)
        return 1

    out_dir = _HERE / "baselines"
    out_dir.mkdir(exist_ok=True)

    asset = "BTC"
    print(f"[ml-train] loading {asset} candles…")
    res_map = {}
    for pkey, p in _TRAIN_PROFILES.items():
        sig = _load_candles(f"{asset}USD", p["sig_res"], db)
        reg = _load_candles(f"{asset}USD", p["reg_res"], db)
        if not sig or not reg:
            print(f"  [{pkey}] missing candle data sig={len(sig)} reg={len(reg)}", file=sys.stderr)
            continue
        for dir_hint in (-1, 1):  # short first (BTC's edge side)
            try:
                report = _train_one(
                    asset, pkey, dir_hint, sig, reg,
                    reg_bar_ms=p["reg_bar_ms"], hold_bars=p["hold_bars"],
                    expected_cost_pct=p["expected_cost_pct"],
                )
            except Exception as exc:
                report = {"asset": asset, "profile_key": pkey,
                          "direction_hint": dir_hint, "error": str(exc)}
            res_map[f"{pkey}_{'long' if dir_hint == 1 else 'short'}"] = report

    date = datetime.utcnow().strftime("%Y%m%d")
    path = out_dir / f"btc_ml_train_{date}.json"
    payload = {
        "run_at": datetime.utcnow().isoformat() + "Z",
        "results": res_map,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"\n[ml-train] wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
