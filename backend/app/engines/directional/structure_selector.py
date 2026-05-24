"""STRATEGY STUB — leverage / structure selection removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. `select_leverage` returns
1 (no leverage) while no strategy is loaded.

Implement the new structure-selection logic here.
"""
from __future__ import annotations


def select_leverage(score: float, signal_strength: str) -> int:
    """Neutral: always 1x (no strategy loaded)."""
    return 1
