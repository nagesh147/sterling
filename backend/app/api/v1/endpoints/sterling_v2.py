from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from app.engines.sterling_v2.config import (
    V2_ENABLED_DEFAULT, V2_PAPER_ONLY, V2_AUTO_EXECUTE,
)
from app.engines.sterling_v2 import data as D, portfolio as PF, research as R

router = APIRouter(prefix="/sterling-v2", tags=["sterling_v2"])


class V2Config(BaseModel):
    enabled: bool = V2_ENABLED_DEFAULT
    paper_only: bool = V2_PAPER_ONLY
    auto_execute: bool = V2_AUTO_EXECUTE


_config = V2Config()


@router.get("/config", response_model=V2Config)
def get_config() -> V2Config:
    return _config


@router.get("/health")
def health() -> dict:
    return {"engine": "sterling_v2", "status": "ready"}


# --- shared, cached data access -------------------------------------------
@lru_cache(maxsize=16)
def _resampled(path: str, tf: str) -> pd.DataFrame:
    """Cache resampled frames so /signals and /backtest don't reload parquet."""
    return D.resample_tf(D.load_symbol(path), tf)


def _portfolio_metrics(eq: pd.Series) -> dict:
    if eq.empty:
        return {"net": 0.0, "max_dd": 0.0, "sharpe": 0.0}
    r = eq.pct_change().dropna()
    peak = eq.cummax()
    max_dd = float(((eq - peak) / peak).min())
    span_days = max((eq.index[-1] - eq.index[0]).days, 1)
    epy = len(r) / (span_days / 365.25)
    sd = r.std(ddof=1) if len(r) >= 2 else 0.0
    sharpe = float(r.mean() / sd * np.sqrt(epy)) if sd > 1e-12 and epy > 0 else 0.0
    return {"net": float(eq.iloc[-1] - 1.0), "max_dd": max_dd, "sharpe": sharpe}


# --- live signals (paper only, auto-execute OFF) --------------------------
@router.get("/signals")
def signals() -> dict:
    """Latest actionable signal per symbol at 4h from the validated V2 stack.
    Paper-only display: this NEVER calls the order router. Execution stays manual."""
    out = []
    for sym, path in D.list_symbols().items():
        d = _resampled(path, R.V2_TF_DEFAULT)
        sig = R.latest_v2_signal(d)
        sig["symbol"] = sym
        sig["tf"] = R.V2_TF_DEFAULT
        sig["strategy"] = R.V2_STRAT_DEFAULT
        out.append(sig)
    return {"signals": out, "paper_only": _config.paper_only,
            "auto_execute": _config.auto_execute}


# --- test-slice backtest of the validated stack ---------------------------
@router.get("/backtest")
def backtest() -> dict:
    """Run the kept-lever V2 stack on the untouched test slice per symbol, then
    combine into a correlation-aware, DD-broken portfolio. Returns per-symbol and
    portfolio test-slice metrics."""
    per_symbol = {}
    curves: dict[str, pd.Series] = {}
    for sym, path in D.list_symbols().items():
        d = _resampled(path, R.V2_TF_DEFAULT)
        _, _, test = R.split_indices(len(d))
        dt = d.iloc[test]
        book = R.run_v2_book(dt)
        m = book["metrics"]
        per_symbol[sym] = {k: round(float(v), 4) for k, v in m.items()}
        if book["returns"].size:
            curves[sym] = book["equity"]

    if len(curves) >= 1:
        if len(curves) >= 2:
            aligned = PF.align_book_returns(curves)  # equal-length, shared grid
            weights = PF.correlation_penalized_weights(aligned)
        else:
            weights = {k: 1.0 for k in curves}
        port_eq = PF.combine_equity(curves, weights, dd_halt=0.20)
        portfolio = {k: round(v, 4) for k, v in _portfolio_metrics(port_eq).items()}
        portfolio["weights"] = {k: round(float(v), 4) for k, v in weights.items()}
    else:
        portfolio = {"net": 0.0, "max_dd": 0.0, "sharpe": 0.0, "weights": {}}

    return {"tf": R.V2_TF_DEFAULT, "strategy": R.V2_STRAT_DEFAULT,
            "adx_min": R.V2_ADX_MIN_DEFAULT, "per_symbol": per_symbol,
            "portfolio": portfolio, "paper_only": _config.paper_only}
