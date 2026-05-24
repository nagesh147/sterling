"""STRATEGY STUB — execution-timing (pullback/continuation) removed in the reset.

Preserved in git history on the `strategy-v2` branch. `assess_timing` returns a
neutral WAIT so the app keeps running with empty states.

Implement the new execution-timing logic here.
"""
from __future__ import annotations

from typing import List

from app.schemas.market import Candle
from app.schemas.directional import ExecTimingResult, ExecMode


def assess_timing(
    candles_15m: List[Candle],
    signal,
    atr_multiplier: float = 1.5,
    atr_pct: float = 0.0,
) -> ExecTimingResult:
    """Neutral timing: always WAIT with zero confidence (no strategy loaded)."""
    return ExecTimingResult(
        mode=ExecMode.WAIT,
        confidence=0.0,
        reason="strategy removed — no timing",
        exec_score=0.0,
    )
