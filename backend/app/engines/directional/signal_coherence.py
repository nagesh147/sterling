"""
Sterling v4 — Signal Coherence.

Measures agreement between the 3 Supertrend channels using variance-based
coherence. High coherence (all 3 agree) → 0 penalty. Low coherence (mixed)
→ signal score deduction.

Used by both `signal_engine.compute_signal` (live) and
`mtf_vectorizer.build_signals_full` (vectorized backtest).
"""
from __future__ import annotations

import numpy as np


def compute_coherence(st_trends: list[int]) -> float:
    """
    Returns 0.0-1.0 coherence between ST channels.

    coherence = 1 - (variance_of_trends / max_variance)
    max_variance = 2.0 for values in {-1, 0, 1}

    1.0 = all channels agree (all +1 or all -1)
    0.5 = 2/3 agree (e.g. [1, 1, -1] or [1, -1, -1])
    0.0 = maximum disagreement (e.g. [1, -1, 0] or equal mix)
    """
    if len(st_trends) < 2:
        return 1.0
    arr = np.array(st_trends, dtype=np.float64)
    mean_t = float(np.mean(arr))
    variance = float(np.mean((arr - mean_t) ** 2))
    max_var = 2.0  # worst case: [1, -1, 0] gives variance = 2/3 * 2.89 ≈ 1.93 ≈ 2
    coherence = 1.0 - (variance / max_var)
    return round(max(0.0, min(1.0, coherence)), 3)


def coherence_penalty(coherence: float, max_penalty: float = 2.0) -> float:
    """
    Converts coherence to a signal-score penalty.

    coherence >= 0.80 → 0 penalty (channels are well-aligned)
    coherence between 0.50 and 0.80 → linear scale
    coherence < 0.50 → max_penalty deduction

    At coherence=0.80: penalty = 0
    At coherence=0.50: penalty = (0.8-0.5)/0.3 * 2.0 = 2.0
    At coherence=0.00: penalty = max_penalty
    """
    if coherence >= 0.80:
        return 0.0
    if coherence >= 0.50:
        return round((0.80 - coherence) / 0.30 * max_penalty, 2)
    return max_penalty