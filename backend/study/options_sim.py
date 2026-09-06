"""Calibrated-BSM options simulation for the derivatives edge study.

Uses the canonical BSM pricing from app.engines.backtest.bs_pricing
and a simplified IV surface calibrated to the live snapshot (Component 4
of the spec). Every result is explicitly labelled "modeled, calibrated
to <date> live surface."

The surface model is intentionally simple (constant shape, scaled by
realized vol × VRP) — this is the honesty bound: a genuine historical
IV series does not exist yet.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import numpy as np
import pandas as pd

from app.engines.backtest.bs_pricing import bs_price, bs_delta
from study.surface_snapshot import SurfaceSnapshot

log = logging.getLogger(__name__)

# Default (sane) values when the snapshot can't provide a measurement
_DEFAULT_IV = 0.18       # conservative Indian index ATM IV fallback
_DEFAULT_VRP = 1.0       # fair
_DEFAULT_SKEW = 0.02     # 2 IV points — mild put skew


def build_iv_surface(snapshot: SurfaceSnapshot | None) -> callable:
    """Return iv(strike, spot, dte, option_type) → float.

    Model: ATM_IV(dte) + skew_adjustment × (delta - 0.5).

    When ATM_IV(dte) is missing (no chain entry for that exact DTE),
    interpolates linearly between the nearest points. Falls back to
    a default IV curve when no snapshot is provided.
    """
    if snapshot is not None and snapshot.atm_iv:
        dtes = np.array(sorted(snapshot.atm_iv.keys()))
        ivs = np.array([snapshot.atm_iv[d] for d in dtes])
    else:
        dtes = np.array([7, 14, 30, 60, 90])
        ivs = np.full_like(dtes, _DEFAULT_IV, float)

    skew = (snapshot.skew_25d if snapshot and snapshot.skew_25d is not None
            else _DEFAULT_SKEW)

    def _iv(strike: float, spot: float, dte: int, option_type: str) -> float:
        # ATM IV at target DTE (linear interpolation)
        atm = float(np.interp(dte, dtes, ivs, left=ivs[0], right=ivs[-1]))

        # Approximate delta for skew adjustment
        approx_delta = bs_delta(spot, strike, dte, atm, option_type)
        if option_type == "put":
            # Skew adds to put IV, subtracts from call IV
            adj = skew * (0.5 - abs(approx_delta))
        else:
            adj = -skew * (0.5 - abs(approx_delta))
        return max(0.01, atm + adj)

    return _iv


def _pick_strike(
    spot: float,
    dte: int,
    target_delta: float,
    option_type: str,
    iv_surface: callable,
    chain_json: str | None = None,
) -> float | None:
    """Find the strike nearest to target_delta.

    Tries the real chain first (if available), falls back to a
    delta-based BSM solver.
    """
    # If we have the real chain, search in it
    if chain_json:
        try:
            chain = json.loads(chain_json)
        except (json.JSONDecodeError, TypeError):
            chain = []
        best_strike = None
        best_dist = float("inf")
        for t in chain:
            if t.get("option_type") != option_type:
                continue
            t_dte = abs((t.get("dte") or 0) - dte)
            if t_dte > 5:  # within 5 DTE
                continue
            delta = abs(t.get("delta") or 0.0)
            dist = abs(delta - abs(target_delta))
            if dist < best_dist:
                best_dist = dist
                best_strike = t.get("strike")
        if best_strike is not None and best_dist < 0.20:
            return float(best_strike)

    # Fallback: BSM solver — iterate over strikes ±30% around spot
    for pct in np.linspace(0.60, 1.40, 81):  # 1% steps
        candidate = round(spot * pct, 0)
        delta = bs_delta(spot, candidate, dte,
                         iv_surface(candidate, spot, dte, option_type),
                         option_type)
        if abs(abs(delta) - abs(target_delta)) < 0.05:
            return candidate
    return None


def simulate_option_config(
    df: pd.DataFrame,
    signals: np.ndarray,
    option_type: str,          # "call" | "put"
    delta_target: float,       # e.g. 0.30 for 30Δ
    dte_entry: int,            # DTE at entry
    iv_surface: callable,
    chain_json: str | None = None,
    hold_bars: int = 50,
    max_hold: int = 200,
    fee_rt: float = 0.001,
) -> dict:
    """Simulate BSM-priced option P&L over historical price moves.

    For each signal bar:
    1. Pick strike nearest to target_delta at entry spot
    2. Price entry premium via BSM
    3. Walk forward hold_bars (or max_hold)
    4. Re-price at exit → P&L = (exit - entry) / entry premium

    The IV is held CONSTANT through the trade (no vol path) — this
    is the core honesty bound: we are measuring directional edge
    priced through a fixed vol surface, not vol-timing edge.
    """
    close = df["close"].to_numpy(float)
    n = len(close)

    trades: list[dict] = []
    idx = np.flatnonzero(signals)
    sp = 0

    while sp < len(idx):
        i = int(idx[sp])
        sp += 1
        if i >= n - hold_bars:
            continue

        spot_entry = close[i]
        strike = _pick_strike(
            spot_entry, dte_entry, delta_target, option_type,
            iv_surface, chain_json,
        )
        if strike is None:
            continue

        iv_entry = iv_surface(strike, spot_entry, dte_entry, option_type)
        entry_premium = bs_price(spot_entry, strike, dte_entry, iv_entry, option_type)
        if entry_premium is None or entry_premium <= 1e-8:
            continue

        xi = min(i + hold_bars, n - 1)
        end = min(i + max_hold, n - 1)
        xp_close = close[xi]

        # Walk forward — early exit at max_hold (time stop)
        if xi == end:
            dte_exit = max(0, dte_entry - (xi - i) * 5)  # ~5min bars
        else:
            dte_exit = max(0, dte_entry - (xi - i) * 5)

        iv_exit = iv_surface(strike, xp_close, dte_exit, option_type)
        exit_premium = bs_price(xp_close, strike, dte_exit, iv_exit, option_type)
        if exit_premium is None:
            exit_premium = 0.0
        # Intrinsic value floor at expiry
        if dte_exit == 0:
            if option_type == "call":
                exit_premium = max(0.0, xp_close - strike)
            else:
                exit_premium = max(0.0, strike - xp_close)

        pnl_pct = (exit_premium - entry_premium) / entry_premium - fee_rt
        trades.append({
            "pnl_pct": pnl_pct,
            "entry_bar": int(i),
            "exit_bar": int(xi),
            "strike": strike,
            "entry_premium": entry_premium,
        })

        while sp < len(idx) and idx[sp] <= xi:
            sp += 1

    n_t = len(trades)
    if n_t == 0:
        return {"trades": [], "metrics": {"trades": 0, "win_rate": 0.0, "pf": 0.0,
                "sharpe": 0.0, "expectancy": 0.0, "net_return": 0.0,
                "pnl_usd": 0.0, "max_dd": 0.0}}
    pnls = [t["pnl_pct"] for t in trades]
    from study.sim import base_metrics, sharpe
    m = base_metrics(pnls)
    m["sharpe"] = round(sharpe(pnls), 4)
    m["trades"] = n_t
    return {"trades": trades, "metrics": m}
