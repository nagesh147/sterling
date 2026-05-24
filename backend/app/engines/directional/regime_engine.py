"""STRATEGY STUB — regime detection removed in the strategy reset.

The prior v4 dual-EMA / ADX / HMM regime engine was stripped so a new strategy
can be built on a clean seam. The original is preserved in git history on the
`strategy-v2` branch. `compute_regime` now returns a neutral IDLE regime so the
rest of the app (endpoints, backtests, UI) keeps running with empty states.

Implement the new regime logic here.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from app.schemas.market import Candle
from app.schemas.directional import RegimeResult, MacroRegime

# Per-process memoisation cache for the (future) regime engine. Kept so test
# fixtures and any warm-cache callers can clear it; unused by the stub.
_REGIME_CACHE: dict = {}


def compute_regime(
    candles_4h: List[Candle],
    ema_period: int = 50,
    macro_filter: str = "adx_4h",
    *,
    idle_strictness: Literal["strict", "loose", "auto"] = "auto",
    hmm_prediction: Optional[Dict[str, Any]] = None,
) -> RegimeResult:
    """Neutral regime: always IDLE with a zero score (no strategy loaded)."""
    close = float(candles_4h[-1].close) if candles_4h else 0.0
    return RegimeResult(
        macro_regime=MacroRegime.IDLE,
        ema50=close,
        close_4h=close,
        score=0.0,
    )
