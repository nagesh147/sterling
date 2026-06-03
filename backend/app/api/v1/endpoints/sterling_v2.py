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


V2_SIGNALS_CONFIG = [
    ("BTC", "4h", "ma_crossover", "Intraday, Aggressive, Intraday_Trailing"),
    ("BTC", "4h", "bb_rsi_reversion", "Aggressive, Intraday, Intraday_Trailing"),
    ("BTC", "4h", "smc", "Intraday"),
    ("BTC", "4h", "price_action", "Intraday"),
    ("BTC", "4h", "vwap_cross", "Intraday"),
    ("BTC", "4h", "breakout", "Intraday"),
    ("ETH", "4h", "price_action", "Intraday"),
    ("ETH", "4h", "smc", "Intraday, Aggressive"),
    ("ETH", "4h", "breakout", "Aggressive, Scalping"),
    ("ETH", "4h", "ma_crossover", "Intraday"),
    ("ETH", "4h", "bb_rsi_reversion", "Scalping"),
    ("SOL", "4h", "smc", "Aggressive"),
    ("SOL", "4h", "price_action", "Intraday"),
    ("SOL", "4h", "vwap_cross", "Intraday_Trailing"),
]

# --- live signals (paper only, auto-execute OFF) --------------------------
@router.get("/signals")
def signals() -> dict:
    """Actionable signals per symbol at 4h from the validated V2 stack based on config.
    Paper-only display: this NEVER calls the order router. Execution stays manual."""
    out = []
    symbols_paths = D.list_symbols()
    for sym, tf, strat, profiles in V2_SIGNALS_CONFIG:
        path = symbols_paths.get(f"{sym}USD") or symbols_paths.get(sym)
        if not path:
            continue
        try:
            d = _resampled(path, tf)
            sig = R.latest_v2_signal(d, strat=strat)
        except Exception as e:
            continue
            
        # Instrument transformation logic
        conv = min(sig.get("conviction", 0.0) / 40.0, 1.0)
        S = sig["entry"]
        stop = sig["stop"]
        target = sig["target"]
        side = sig["side"]
        atr = sig.get("atr", 0.0)
        
        if side != 0 and S > 0 and stop and target:
            stop_pct = abs(S - stop) / S
            M = abs(target - S)
            
            # 1. SPOT setup
            spot_sig = sig.copy()
            spot_sig["instrument_type"] = "spot"
            spot_sig["leverage"] = 1.0
            spot_sig["margin"] = S # Notional
            spot_sig["risk_pct"] = stop_pct
            
            # 2. FUTURES setup
            fut_sig = sig.copy()
            fut_sig["instrument_type"] = "futures"
            profile_cap = 10 if "Aggressive" in profiles else 3 if "Scalping" in profiles else 5
            liq_buffer = 0.005
            maint_margin = 0.005
            L_max_liq = 1.0 / (stop_pct + liq_buffer + maint_margin) if (stop_pct + liq_buffer + maint_margin) > 0 else 1.0
            L = min(L_max_liq, profile_cap)
            fut_sig["leverage"] = round(L, 1)
            fut_sig["margin"] = S / L if L > 0 else S
            fut_sig["risk_pct"] = stop_pct * L
            
            # 3. OPTIONS setup
            opt_sig = sig.copy()
            opt_sig["instrument_type"] = "options"
            opt_sig["option_type"] = "call" if side == 1 else "put"
            expected_hold_bars = 6
            T_days = expected_hold_bars * 4 * 1.5 / 24.0 # expected hold in days
            opt_sig["expiry_days"] = max(round(T_days, 1), 1.0)
            
            # Strike logic
            if conv > 0.6 and M > atr * 2:
                opt_sig["strike"] = S + (0.5 * atr * side) # OTM
            else:
                opt_sig["strike"] = S # ATM
            opt_sig["strike"] = round(opt_sig["strike"], 2)
            
            # Premium proxy
            sigma_annual = (atr / S) * np.sqrt(6 * 365) if S > 0 else 0
            premium = 0.4 * S * sigma_annual * np.sqrt(opt_sig["expiry_days"] / 365.0)
            opt_sig["premium"] = premium
            opt_sig["max_loss"] = premium
            opt_sig["breakeven_pct"] = premium / S if S > 0 else 0
            
            # Picker Score
            trendy = 1 if strat in ["ma_crossover", "breakout", "vwap_cross"] else 0
            reverting = 1 if strat == "bb_rsi_reversion" else 0
            move_be = M / premium if premium > 0 else 0
            funding_drag = 0.0001
            liq_penalty = 0.1 if L == L_max_liq else 0
            
            score_spot = 0.5 * reverting + 0.3 * (1 - conv) + 0.2 * (1 if premium/S > M/S else 0)
            score_futures = 0.35 * conv + 0.30 * trendy + 0.20 * (1 - stop_pct) - 0.15 * funding_drag - liq_penalty
            score_options = 0.35 * min(max(move_be - 1, 0), 2) + 0.25 * conv + 0.20 * (1 if stop_pct > 0.05 else 0) - 0.2 * reverting
            
            scores = {"spot": score_spot, "futures": score_futures, "options": score_options}
            best_instr = max(scores, key=scores.get)
            
            instrument_sigs = [spot_sig, fut_sig, opt_sig]
        else:
            # Idle fallback
            base = sig.copy()
            instrument_sigs = []
            for itype in ["spot", "futures", "options"]:
                s = base.copy()
                s["instrument_type"] = itype
                instrument_sigs.append(s)
            best_instr = "spot"
            
        for profile in profiles.split(","):
            for s_base in instrument_sigs:
                s = s_base.copy()
                s["symbol"] = sym
                s["tf"] = tf
                s["strategy"] = strat
                s["profile"] = profile.strip()
                s["recommended"] = (s["instrument_type"] == best_instr)
                
                # Additional fields to match UI expectation
                s["sigId"] = f"{sym}-{strat}-{profile.strip()}-{s['instrument_type']}"
                s["underlying"] = sym
                s["direction"] = "long" if s.get("side", 0) == 1 else "short" if s.get("side", 0) == -1 else "flat"
                s["spot_price"] = s.get("entry", 0)
                s["current_price"] = sig.get("current_price", s.get("entry", 0))
                s["target_price"] = s.get("target")
                s["stop_price"] = s.get("stop")
                
                try:
                    s["timestamp_ms"] = int(pd.Timestamp(s["bar_time"]).timestamp() * 1000)
                except Exception:
                    s["timestamp_ms"] = 0
                    
                out.append(s)
            
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
