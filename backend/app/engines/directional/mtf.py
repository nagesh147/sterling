"""STRATEGY STUB — multi-timeframe score breakdown removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. `compute_mtf_breakdown`
returns a zeroed breakdown so the UI MTF panel renders an empty/neutral state.

Implement the new MTF decomposition here.
"""
from __future__ import annotations

from typing import Any, Dict


def compute_mtf_breakdown(regime, signal, exec_timing) -> Dict[str, Any]:
    """Neutral breakdown: all component scores zero, no alignment."""
    return {
        "macro_4h": 0.0,
        "signal_1h": 0.0,
        "execution_15m": 0.0,
        "alignment": "none",
    }
