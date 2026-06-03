"""Lever 5 -- correlation-aware portfolio combiner + drawdown circuit breaker.

Offline (backtest) combiner: given per-book return series (or equity curves),
allocate inversely to each book's volatility, optionally down-weight books that
are highly correlated with the rest (so a redundant cluster cannot dominate),
then combine and apply a hard portfolio-level drawdown circuit breaker.

Correlations here are computed offline with pandas `.corr()` on the aligned
return matrix -- the right tool for a batch of series. The LIVE path uses the
existing streaming `CorrelationTracker` singleton instead (see Task 13); this
module is import-clean and does not touch that live state.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def inverse_vol_weights(per_book_returns: dict[str, np.ndarray]) -> dict[str, float]:
    """Allocate inversely to each book's return volatility (risk parity-ish).
    A zero-variance or singleton book gets zero weight (no risk estimate)."""
    inv = {k: (1.0 / v.std(ddof=1)) if v.size > 1 and v.std(ddof=1) > 0 else 0.0
           for k, v in per_book_returns.items()}
    tot = sum(inv.values()) or 1.0
    return {k: x / tot for k, x in inv.items()}


def correlation_penalized_weights(per_book_returns: dict[str, np.ndarray],
                                  lam: float = 1.0) -> dict[str, float]:
    """Inverse-vol weights, then down-weight each book by its average absolute
    correlation to the others: w_k *= 1 / (1 + lam * mean_j!=k |corr(k, j)|).
    Books in a highly-correlated cluster are penalized so they cannot crowd out
    diversifying books. Requires equal-length aligned return arrays. Falls back
    to inverse-vol when there are fewer than two books."""
    base = inverse_vol_weights(per_book_returns)
    keys = list(per_book_returns.keys())
    if len(keys) < 2:
        return base
    corr = pd.DataFrame({k: per_book_returns[k] for k in keys}).corr().to_numpy()
    adj = {}
    for i, k in enumerate(keys):
        others = [abs(corr[i, j]) for j in range(len(keys))
                  if j != i and np.isfinite(corr[i, j])]
        avg_corr = float(np.mean(others)) if others else 0.0
        adj[k] = base[k] / (1.0 + lam * avg_corr)
    tot = sum(adj.values()) or 1.0
    return {k: x / tot for k, x in adj.items()}


def align_book_returns(per_book_curves: dict[str, pd.Series]) -> dict[str, np.ndarray]:
    """Project per-book equity curves onto a shared time index and return their
    equal-length period returns -- the correct input for the weight functions
    (per-trade returns of different books are not comparable element-wise)."""
    idx = sorted(set().union(*[c.index for c in per_book_curves.values()]))
    aligned = pd.DataFrame({k: c.reindex(idx).ffill().fillna(1.0)
                            for k, c in per_book_curves.items()})
    rets = aligned.pct_change().fillna(0.0)
    return {k: rets[k].to_numpy() for k in rets.columns}


def combine_equity(per_book_curves: dict[str, pd.Series],
                   weights: dict[str, float],
                   dd_halt: float = 0.20) -> pd.Series:
    """Combine per-book equity curves on a shared time index with weights, then
    apply a hard drawdown circuit breaker: once portfolio DD <= -dd_halt, flatten
    (equity held constant) for the rest of the series."""
    idx = sorted(set().union(*[c.index for c in per_book_curves.values()]))
    aligned = pd.DataFrame({k: c.reindex(idx).ffill().fillna(1.0)
                            for k, c in per_book_curves.items()})
    rets = aligned.pct_change().fillna(0.0)
    port_ret = (rets * pd.Series(weights)).sum(axis=1)
    eq = (1 + port_ret).cumprod()
    peak = eq.cummax()
    dd = (eq - peak) / peak
    halt_at = dd[dd <= -dd_halt].index.min() if (dd <= -dd_halt).any() else None
    if halt_at is not None:
        eq.loc[halt_at:] = eq.loc[halt_at]
    return eq
