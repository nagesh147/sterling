"""STRATEGY STUB — track ensemble scoring removed in the strategy reset.

The prior ensemble combined Trend-Following / VCP / Mean-Reversion track signals
into a composite direction + score. It was stripped (preserved in git history on
the `strategy-v2` branch). Only the active-strategy selector API is kept so the
trading-mode endpoint and startup wiring keep working; the names are inert
placeholders until a new ensemble is implemented.

Implement the new ensemble scoring here.
"""
from __future__ import annotations

import os
from typing import Dict, Optional

# Legacy names kept so the UI strategy dropdown / persisted config still resolve.
AVAILABLE_STRATEGIES: Dict[str, Optional[object]] = {
    "by_edge_max_linear_agree": None,
    "unweighted_mean": None,
}

_ACTIVE_STRATEGY: str = os.environ.get(
    "STERLING_SCORING_STRATEGY", "by_edge_max_linear_agree"
)


def get_active_strategy() -> str:
    return _ACTIVE_STRATEGY


def set_strategy(name: str) -> None:
    """Tolerant: records the selected name; there is no logic to validate yet."""
    global _ACTIVE_STRATEGY
    _ACTIVE_STRATEGY = name
