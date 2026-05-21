"""
Sterling v4 Phase 3 — On-disk model persistence.

Stores xgboost Boosters per (asset, profile_key) at a canonical path so the
ML ensemble track can load the right model at compute time.

Path layout:
    backend/models/<asset>_<profile_key>.xgb          (Booster binary)
    backend/models/<asset>_<profile_key>.meta.json    (feature names, train metadata)

Pure local-disk. No remote upload. Backup with `git lfs` or a separate
artefact store if needed for production deployment.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


_DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "models"


@dataclass(frozen=True)
class ModelMeta:
    """Metadata persisted alongside the binary."""
    asset:               str
    profile_key:         str
    direction_hint:      int
    feature_names:       List[str]
    n_train_bars:        int
    oos_sharpe:          float
    deflated_sharpe:     Optional[float]
    fold_test_sharpes:   List[float]
    feature_importance:  Dict[str, float]
    stable_features:     List[str]
    trained_at:          str
    profitable_mult:     float
    hold_bars:           int
    expected_cost_pct:   float
    notes:               str = ""


def _paths(asset: str, profile_key: str,
           root: Optional[Path] = None) -> tuple[Path, Path]:
    r = root or _DEFAULT_ROOT
    r.mkdir(parents=True, exist_ok=True)
    safe_asset = asset.upper().replace("/", "_")
    base = r / f"{safe_asset}_{profile_key}"
    return base.with_suffix(".xgb"), base.with_suffix(".meta.json")


def save_model(
    booster: Any,
    meta:    ModelMeta,
    root:    Optional[Path] = None,
) -> tuple[Path, Path]:
    """Persist a Booster + meta. Returns (model_path, meta_path)."""
    model_path, meta_path = _paths(meta.asset, meta.profile_key, root)
    booster.save_model(str(model_path))
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(asdict(meta), f, indent=2, default=str)
    return model_path, meta_path


def load_model(
    asset:       str,
    profile_key: str,
    root:        Optional[Path] = None,
) -> Optional[tuple[Any, ModelMeta]]:
    """Load a Booster + meta. Returns None when no model exists on disk."""
    try:
        import xgboost as xgb
    except Exception:
        return None
    model_path, meta_path = _paths(asset, profile_key, root)
    if not model_path.exists() or not meta_path.exists():
        return None
    booster = xgb.Booster()
    booster.load_model(str(model_path))
    with open(meta_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    meta = ModelMeta(
        asset=m["asset"], profile_key=m["profile_key"],
        direction_hint=int(m["direction_hint"]),
        feature_names=list(m["feature_names"]),
        n_train_bars=int(m["n_train_bars"]),
        oos_sharpe=float(m["oos_sharpe"]),
        deflated_sharpe=(None if m.get("deflated_sharpe") in (None, "None")
                         else float(m["deflated_sharpe"])),
        fold_test_sharpes=[float(x) for x in m.get("fold_test_sharpes", [])],
        feature_importance={k: float(v) for k, v in m.get("feature_importance", {}).items()},
        stable_features=list(m.get("stable_features", [])),
        trained_at=str(m.get("trained_at", "")),
        profitable_mult=float(m.get("profitable_mult", 2.0)),
        hold_bars=int(m.get("hold_bars", 16)),
        expected_cost_pct=float(m.get("expected_cost_pct", 0.005)),
        notes=str(m.get("notes", "")),
    )
    return booster, meta


def list_models(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """List all persisted (asset, profile_key) model summaries."""
    r = root or _DEFAULT_ROOT
    if not r.exists():
        return []
    out = []
    for meta_path in sorted(r.glob("*.meta.json")):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                m = json.load(f)
            out.append({
                "asset":           m.get("asset"),
                "profile_key":     m.get("profile_key"),
                "oos_sharpe":      m.get("oos_sharpe"),
                "deflated_sharpe": m.get("deflated_sharpe"),
                "trained_at":      m.get("trained_at"),
                "model_path":      str(meta_path.with_suffix("")) + ".xgb",
            })
        except Exception:
            continue
    return out
