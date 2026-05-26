"""STRATEGY STUB — leverage / structure selection removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. `select_leverage` returns
1 (no leverage) while no strategy is loaded.

Implement the new structure-selection logic here.
"""
from __future__ import annotations


def select_leverage(score: float, signal_strength: str) -> int:
    """v3 leverage scale: maps 0-100 score to leverage."""
    
    if signal_strength != "STRONG" and score < 75:
        return 1
        
    if score >= 95:
        return 50
    elif score >= 90:
        return 25
    elif score >= 85:
        return 10
    elif score >= 80:
        return 5
    elif score >= 75:
        return 3
        
    return 1
