"""Robustness validation gates (CPCV + Monte Carlo).

Wraps the existing analytics modules to apply OOS-only gates on the
derivatives study configs. Only runs on configs that survive the
cheap base-metrics filter first (net-positive, trades ≥ 50).
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from app.engines.analytics.cpcv import calculate_pbo
from app.engines.analytics.monte_carlo import monte_carlo_trades

log = logging.getLogger(__name__)

# ── Gate thresholds (aligned with robustness_scan.py + EdgeGate) ───────
MIN_TRADES = 50
MAX_P_LOSS = 0.35
MIN_OOS_SHARPE = 0.0  # must be positive
N_MC_SIMS = 3000
CPCV_N_GROUPS = 6
CPCV_K_TEST = 2
CPCV_TRAIN_MIN_TRADES = 15
SEED = 42


def robustness_gate(
    trades: list[dict],
    *,
    min_trades: int = MIN_TRADES,
    max_p_loss: float = MAX_P_LOSS,
    n_mc: int = N_MC_SIMS,
    seed: int = SEED,
) -> dict:
    """Apply CPCV + Monte Carlo gates to a single config's trades.

    Returns a dict with all robustness metrics plus a `survived`
    boolean. Configs with fewer than min_trades are automatically
    rejected (CPCV can't run meaningfully below ~30 trades).
    """
    n = len(trades)
    if n < min_trades:
        return {
            "survived": False,
            "reason": f"insufficient_trades:{n}<{min_trades}",
            "n_trades": n,
            "oos_sharpe": 0.0,
            "p_loss": 1.0,
            "is_oos_correlation": None,
            "oos_keep": 0.0,
            "mc_ret_p05": 0.0,
            "mc_dd_p05": 0.0,
        }

    pnls = [t["pnl_pct"] for t in trades]
    holds = [t.get("exit_bar", 0) - t.get("entry_bar", 0) for t in trades]
    hb = max(1, int(np.median(holds)))

    # ── CPCV ────────────────────────────────────────────────────────────
    try:
        cp = calculate_pbo(
            trades,
            hold_bars=hb,
            n_groups=CPCV_N_GROUPS,
            k_test=CPCV_K_TEST,
            train_min_trades=CPCV_TRAIN_MIN_TRADES,
        )
    except Exception:
        log.exception("CPCV failed for %d trades", n)
        cp = {
            "mean_train_sharpe": 0.0,
            "mean_test_sharpe": 0.0,
            "warnings": ["cpcv_error"],
        }

    oos_sharpe = round(float(cp.get("mean_test_sharpe", 0.0)), 4)
    is_sharpe = round(float(cp.get("mean_train_sharpe", 0.0)), 4)
    oos_keep = round(oos_sharpe / is_sharpe, 2) if is_sharpe else 0.0

    # IS↔OOS correlation (if available from paths)
    paths = cp.get("paths", [])
    is_oos_correlation = None
    if len(paths) >= 3:
        is_vals = np.array([p["train_sharpe"] for p in paths])
        oos_vals = np.array([p["test_sharpe"] for p in paths])
        if np.std(is_vals) > 0 and np.std(oos_vals) > 0:
            is_oos_correlation = round(float(np.corrcoef(is_vals, oos_vals)[0, 1]), 4)

    # ── Monte Carlo ─────────────────────────────────────────────────────
    try:
        mc = monte_carlo_trades(pnls, n_sims=n_mc, seed=seed, method="bootstrap")
    except Exception:
        log.exception("Monte Carlo failed for %d trades", n)
        mc_ret_p05 = mc_dd_p05 = 0.0
        p_loss = 1.0
    else:
        mc_ret_p05 = round(float(mc.return_pct_p05), 1)
        mc_dd_p05 = round(float(mc.max_dd_pct_p05), 1)
        p_loss = round(float(mc.prob_loss), 4)

    survived = (oos_sharpe > MIN_OOS_SHARPE) and (p_loss <= max_p_loss)

    reason = "ok" if survived else (
        f"oos_sharpe:{oos_sharpe:.3f}<={MIN_OOS_SHARPE}" if oos_sharpe <= MIN_OOS_SHARPE
        else f"p_loss:{p_loss:.3f}>{max_p_loss}"
    )

    return {
        "survived": survived,
        "reason": reason,
        "n_trades": n,
        "oos_sharpe": oos_sharpe,
        "is_sharpe": is_sharpe,
        "oos_keep": oos_keep,
        "is_oos_correlation": is_oos_correlation,
        "p_loss": p_loss,
        "mc_ret_p05": mc_ret_p05,
        "mc_dd_p05": mc_dd_p05,
        "cpcv_warnings": cp.get("warnings", []),
    }
