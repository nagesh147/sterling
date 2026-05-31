"""Monte Carlo robustness on a trade-return sequence.

Pure module — no I/O. A backtest's headline return and max drawdown are a
SINGLE draw from a random process. Resampling the per-trade returns many times
yields a distribution, so consumers get confidence bands rather than a point
estimate.

Two resampling methods:

  reorder   — shuffle the SAME multiset of trades (sampling WITHOUT replacement).
              Final compounded return is identical on every path; only the
              equity PATH (and therefore max drawdown) changes. Isolates
              *sequence risk* — "could the same trades, in a worse order, have
              blown through my drawdown tolerance?"

  bootstrap — sample WITH replacement. Both the final return AND the drawdown
              vary. Approximates *sampling risk* — "if the next N trades are
              drawn from the same distribution, what's the spread of outcomes?"

Returns are decimal per-trade P&L fractions (0.02 = +2%), compounded.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np


@dataclass
class MonteCarloResult:
    n_trades: int
    n_sims: int
    method: str
    # Final compounded return (%) percentiles across simulated paths.
    return_pct_p05: float
    return_pct_p50: float
    return_pct_p95: float
    return_pct_mean: float
    # Max drawdown (%, negative) percentiles. p05 = worst (most negative).
    max_dd_pct_p05: float
    max_dd_pct_p50: float
    max_dd_pct_p95: float
    # Probability a path ends below the starting capital.
    prob_loss: float


def _empty(n_sims: int, method: str) -> MonteCarloResult:
    return MonteCarloResult(
        n_trades=0, n_sims=n_sims, method=method,
        return_pct_p05=0.0, return_pct_p50=0.0, return_pct_p95=0.0,
        return_pct_mean=0.0, max_dd_pct_p05=0.0, max_dd_pct_p50=0.0,
        max_dd_pct_p95=0.0, prob_loss=0.0,
    )


def _path_stats(seq: np.ndarray) -> tuple[float, float]:
    """Compound a return sequence → (final_return_pct, max_drawdown_pct)."""
    equity = np.cumprod(1.0 + seq)
    final_ret = (equity[-1] - 1.0) * 100.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return final_ret, float(dd.min()) * 100.0


def monte_carlo_trades(
    returns: Sequence[float],
    *,
    n_sims: int = 10_000,
    method: str = "reorder",
    seed: Optional[int] = None,
) -> MonteCarloResult:
    """Resample `returns` `n_sims` times and report return / drawdown bands.

    method: "reorder" (shuffle, no replacement) or "bootstrap" (with replacement).
    """
    arr = np.asarray([float(r) for r in returns], dtype=np.float64)
    n = arr.size
    if n == 0:
        return _empty(n_sims, method)

    rng = np.random.default_rng(seed)
    finals = np.empty(n_sims, dtype=np.float64)
    dds = np.empty(n_sims, dtype=np.float64)

    for s in range(n_sims):
        if method == "bootstrap":
            seq = arr[rng.integers(0, n, size=n)]
        else:  # reorder
            seq = arr[rng.permutation(n)]
        finals[s], dds[s] = _path_stats(seq)

    return MonteCarloResult(
        n_trades=n, n_sims=n_sims, method=method,
        return_pct_p05=float(np.percentile(finals, 5)),
        return_pct_p50=float(np.percentile(finals, 50)),
        return_pct_p95=float(np.percentile(finals, 95)),
        return_pct_mean=float(finals.mean()),
        max_dd_pct_p05=float(np.percentile(dds, 5)),
        max_dd_pct_p50=float(np.percentile(dds, 50)),
        max_dd_pct_p95=float(np.percentile(dds, 95)),
        prob_loss=float(np.mean(finals < 0.0)),
    )
