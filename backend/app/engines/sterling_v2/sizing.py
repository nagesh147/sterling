"""Lever 4 -- volatility-targeted per-trade sizing.

`vol_target_weights` scales each trade toward a target per-trade volatility using
a TRAILING std of prior realized trade returns (returns[:i] only), so the weight
for trade i uses no information from trade i or later -- leak-free. Applied via
`harness.compute_metrics(res, weights=...)`.
"""
from __future__ import annotations

import numpy as np


def vol_target_weights(returns: np.ndarray, target_vol: float = 0.02,
                       cap: float = 3.0) -> np.ndarray:
    """Per-trade weight scaling trades toward a target per-trade volatility.
    weight_i = clip(target_vol / trailing_std_i, 0, cap), where trailing_std_i is
    the std of returns[:i] (strictly prior trades). The first 5 trades and any
    zero-variance prefix get weight 1.0 (no estimate yet)."""
    n = returns.size
    w = np.ones(n)
    for i in range(n):
        if i < 5:
            continue
        tr = returns[:i].std(ddof=1)
        w[i] = min(cap, target_vol / tr) if tr > 0 else 1.0
    return w
