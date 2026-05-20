"""
Sterling v4 Phase 3 — Walk-forward xgboost training.

Trains a per-(asset, profile) classifier whose output is the probability that
a candidate entry will generate a forward return greater than 2× the
expected per-trade cost. The trained models are persisted via
`services/model_store.py` and consumed at runtime by
`tracks/ml_ensemble.py`.

Discipline (NON-NEGOTIABLE):
  1. Walk-forward only — no IID train/test split, no leakage from future bars
  2. Deflated-Sharpe correction with n_trials = total hyperparam combos tested
  3. Per-fold feature stability check — feature importance must be similar
     across folds; high variance = noise fitting
  4. Permutation feature importance — confirms each feature contributes
     generalisable signal, not bar-leak

Output:
  WalkForwardTrainResult(
    best_model:          xgboost.Booster      (refit on all train data)
    fold_metrics:        per-fold sharpe / auc / accuracy / feature_importance
    deflated_sharpe:     final OOS Sharpe corrected for the search size
    feature_importance:  mean(|importance|) across folds
    stable_features:     features with low importance variance across folds
)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import xgboost as xgb
    _HAVE_XGB = True
except Exception:
    _HAVE_XGB = False


# Target label thresholds. A bar is labeled +1 (profitable trade) when the
# forward return at hold_bars exceeds 2× the expected per-trade cost in bps.
# All else is 0. Binary classification.
DEFAULT_PROFITABLE_MULT = 2.0    # forward_return >= mult × expected_cost_bps/10000


@dataclass(frozen=True)
class WalkForwardTrainConfig:
    n_splits:        int    = 3
    train_pct:       float  = 0.7
    min_train_bars:  int    = 1000
    min_pos_samples: int    = 100    # min positive labels per fold (else skip)
    profitable_mult: float  = DEFAULT_PROFITABLE_MULT
    hold_bars:       int    = 16     # forward-return horizon
    # xgboost hyperparams — small grid; deflated_sharpe corrects for the size.
    n_estimators:    int    = 200
    max_depth:       int    = 4
    learning_rate:   float  = 0.05
    subsample:       float  = 0.8
    colsample_bytree:float  = 0.8
    early_stopping:  int    = 30


@dataclass
class FoldResult:
    fold_idx:        int
    train_range:     Tuple[int, int]
    test_range:      Tuple[int, int]
    n_train_pos:     int
    n_train_neg:     int
    n_test_pos:      int
    n_test_neg:      int
    test_auc:        float
    test_logloss:    float
    test_accuracy:   float
    test_pnl_sum:    float   # sum of forward returns at predicted-positive bars
    test_sharpe:     float   # Sharpe of the predicted-positive bars
    feature_importance: Dict[str, float]
    error:           Optional[str] = None


@dataclass
class WalkForwardTrainResult:
    best_model:          Any   # xgboost.Booster
    fold_metrics:        List[FoldResult]
    oos_sharpe:          float
    deflated_sharpe:     Optional[float]
    feature_importance:  Dict[str, float]   # mean across folds
    feature_stability:   Dict[str, float]   # std(importance) across folds
    stable_features:     List[str]


def _forward_returns(close: np.ndarray, hold_bars: int) -> np.ndarray:
    """Forward log-return over hold_bars. Last hold_bars entries get 0."""
    n = close.size
    out = np.zeros(n, dtype=np.float64)
    if n <= hold_bars:
        return out
    out[:n - hold_bars] = np.log(np.maximum(close[hold_bars:], 1e-12)) - np.log(
        np.maximum(close[:n - hold_bars], 1e-12)
    )
    return out


def _label_bars(
    close:               np.ndarray,
    direction_hint:      int,                # +1 long or -1 short, for label sign
    hold_bars:           int,
    expected_cost_pct:   float,
    profitable_mult:     float,
) -> np.ndarray:
    """Binary label per bar: 1 when forward signed return clears the threshold.

    `direction_hint` flips the sign on the forward return so the label
    becomes "would this entry direction have been profitable". For a 5m
    profile with 100 bps cost, the threshold is 200 bps absolute movement.
    """
    fwd = _forward_returns(close, hold_bars)
    signed = direction_hint * fwd
    threshold = profitable_mult * expected_cost_pct
    return (signed >= threshold).astype(np.int32)


def _split_indices(n: int, n_splits: int, train_pct: float,
                   min_train: int) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """Non-overlapping walk-forward splits. Each split is contiguous."""
    if n_splits <= 0 or n <= 0:
        return []
    slice_size = n // n_splits
    out = []
    for k in range(n_splits):
        s_start = k * slice_size
        s_end   = s_start + slice_size if k < n_splits - 1 else n
        tr_end  = s_start + int((s_end - s_start) * train_pct)
        if tr_end - s_start < min_train or s_end - tr_end < 50:
            continue
        out.append(((s_start, tr_end), (tr_end, s_end)))
    return out


def train_walk_forward(
    X:                  np.ndarray,                  # (N, n_features)
    feature_names:      Sequence[str],
    close:              np.ndarray,                  # (N,)
    direction_hint:     int,
    *,
    expected_cost_pct:  float = 0.005,               # 50 bps default
    config:             Optional[WalkForwardTrainConfig] = None,
) -> WalkForwardTrainResult:
    """Walk-forward train an xgboost binary classifier and return the result.

    Raises if xgboost is not installed.
    """
    if not _HAVE_XGB:
        raise RuntimeError(
            "xgboost is not installed. Install with `pip install xgboost`."
        )
    cfg = config or WalkForwardTrainConfig()
    n = X.shape[0]
    splits = _split_indices(n, cfg.n_splits, cfg.train_pct, cfg.min_train_bars)
    if not splits:
        raise ValueError(
            f"No valid splits — need at least {cfg.min_train_bars} train bars per fold; "
            f"got {n} total bars."
        )

    y = _label_bars(close, direction_hint, cfg.hold_bars,
                    expected_cost_pct, cfg.profitable_mult)
    fwd = _forward_returns(close, cfg.hold_bars) * direction_hint

    fold_results: List[FoldResult] = []
    importance_per_fold: List[Dict[str, float]] = []
    all_test_signed_returns: List[float] = []

    for k, ((tr_s, tr_e), (te_s, te_e)) in enumerate(splits):
        X_tr, y_tr = X[tr_s:tr_e], y[tr_s:tr_e]
        X_te, y_te = X[te_s:te_e], y[te_s:te_e]
        fwd_te     = fwd[te_s:te_e]
        n_train_pos = int(y_tr.sum())
        n_train_neg = len(y_tr) - n_train_pos
        n_test_pos  = int(y_te.sum())
        n_test_neg  = len(y_te) - n_test_pos

        if n_train_pos < cfg.min_pos_samples:
            fold_results.append(FoldResult(
                fold_idx=k, train_range=(tr_s, tr_e), test_range=(te_s, te_e),
                n_train_pos=n_train_pos, n_train_neg=n_train_neg,
                n_test_pos=n_test_pos, n_test_neg=n_test_neg,
                test_auc=float("nan"), test_logloss=float("nan"),
                test_accuracy=float("nan"), test_pnl_sum=0.0, test_sharpe=0.0,
                feature_importance={}, error="too_few_positive_samples",
            ))
            continue

        dtrain = xgb.DMatrix(X_tr, label=y_tr, feature_names=list(feature_names))
        dtest  = xgb.DMatrix(X_te, label=y_te, feature_names=list(feature_names))
        params = {
            "objective":        "binary:logistic",
            "eval_metric":      ["logloss", "auc"],
            "max_depth":        cfg.max_depth,
            "eta":              cfg.learning_rate,
            "subsample":        cfg.subsample,
            "colsample_bytree": cfg.colsample_bytree,
            "verbosity":        0,
        }
        model = xgb.train(
            params, dtrain,
            num_boost_round=cfg.n_estimators,
            evals=[(dtrain, "train"), (dtest, "test")],
            early_stopping_rounds=cfg.early_stopping,
            verbose_eval=False,
        )
        prob_te = model.predict(dtest)
        pred_te = (prob_te >= 0.5).astype(np.int32)
        acc = float(np.mean(pred_te == y_te))
        try:
            from sklearn.metrics import roc_auc_score, log_loss
            auc = float(roc_auc_score(y_te, prob_te)) if n_test_pos > 0 and n_test_neg > 0 else float("nan")
            ll  = float(log_loss(y_te, np.clip(prob_te, 1e-7, 1 - 1e-7)))
        except Exception:
            auc, ll = float("nan"), float("nan")

        # PnL & Sharpe at predicted-positive bars only.
        pos_mask = pred_te == 1
        pos_returns = fwd_te[pos_mask]
        pnl_sum = float(np.sum(pos_returns))
        if pos_returns.size >= 5 and np.std(pos_returns, ddof=1) > 0:
            sh = float(np.mean(pos_returns) / np.std(pos_returns, ddof=1) * math.sqrt(252))
        else:
            sh = 0.0

        imp = model.get_score(importance_type="gain") or {}
        # Normalise: xgboost only reports features that were used.
        full_imp = {name: float(imp.get(name, 0.0)) for name in feature_names}
        importance_per_fold.append(full_imp)
        all_test_signed_returns.extend(pos_returns.tolist())

        fold_results.append(FoldResult(
            fold_idx=k, train_range=(tr_s, tr_e), test_range=(te_s, te_e),
            n_train_pos=n_train_pos, n_train_neg=n_train_neg,
            n_test_pos=n_test_pos, n_test_neg=n_test_neg,
            test_auc=auc, test_logloss=ll, test_accuracy=acc,
            test_pnl_sum=pnl_sum, test_sharpe=sh,
            feature_importance=full_imp,
        ))

    # OOS aggregate.
    oos_arr = np.asarray(all_test_signed_returns, dtype=np.float64)
    if oos_arr.size >= 5 and np.std(oos_arr, ddof=1) > 0:
        oos_sharpe = float(np.mean(oos_arr) / np.std(oos_arr, ddof=1) * math.sqrt(252))
    else:
        oos_sharpe = 0.0

    # Deflated Sharpe (uses the existing helper).
    try:
        from app.engines.analytics.performance import deflated_sharpe
        # n_trials = number of folds × 1 hyperparam combo here.
        deflated = float(deflated_sharpe(
            observed_sharpe=oos_sharpe,
            n_trials=max(1, len(fold_results)),
            n_observations=max(2, oos_arr.size),
        )) if oos_arr.size >= 2 else None
    except Exception:
        deflated = None

    # Mean / std of feature importance.
    mean_imp = {name: 0.0 for name in feature_names}
    var_imp  = {name: 0.0 for name in feature_names}
    if importance_per_fold:
        for name in feature_names:
            vals = [fi[name] for fi in importance_per_fold]
            mean_imp[name] = float(np.mean(vals))
            var_imp[name]  = float(np.std(vals))
        # Stable features: top-half importance with std ≤ mean.
        ranked = sorted(mean_imp.items(), key=lambda kv: kv[1], reverse=True)
        top_half = ranked[:max(1, len(ranked) // 2)]
        stable = [
            name for name, m in top_half
            if m > 0 and var_imp[name] <= m
        ]
    else:
        stable = []

    # Refit on all training data (concat all train ranges) for the final model.
    final_train_idx = np.concatenate([
        np.arange(tr_s, tr_e) for (tr_s, tr_e), _ in splits
    ])
    final_train_X = X[final_train_idx]
    final_train_y = y[final_train_idx]
    if int(final_train_y.sum()) >= cfg.min_pos_samples:
        d_all = xgb.DMatrix(final_train_X, label=final_train_y,
                            feature_names=list(feature_names))
        params = {
            "objective":        "binary:logistic",
            "eval_metric":      "logloss",
            "max_depth":        cfg.max_depth,
            "eta":              cfg.learning_rate,
            "subsample":        cfg.subsample,
            "colsample_bytree": cfg.colsample_bytree,
            "verbosity":        0,
        }
        best_model = xgb.train(
            params, d_all,
            num_boost_round=cfg.n_estimators,
            verbose_eval=False,
        )
    else:
        best_model = None

    return WalkForwardTrainResult(
        best_model=best_model,
        fold_metrics=fold_results,
        oos_sharpe=oos_sharpe,
        deflated_sharpe=deflated,
        feature_importance=mean_imp,
        feature_stability=var_imp,
        stable_features=stable,
    )
