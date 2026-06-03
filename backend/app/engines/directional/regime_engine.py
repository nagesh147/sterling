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
    """Computes a basic EMA-based regime."""
    if not candles_4h:
        return RegimeResult(
            macro_regime=MacroRegime.IDLE,
            ema50=0.0,
            close_4h=0.0,
            score=0.0,
        )

    # Basic EMA calculation
    closes = [float(c.close) for c in candles_4h]
    ema_period = 5
    alpha = 2 / (ema_period + 1)
    ema = closes[0]
    for c in closes[1:]:
        ema = (c - ema) * alpha + ema

    close = closes[-1]
    
    if close > ema:
        regime = MacroRegime.BULL_TREND
        score = 80.0
    else:
        regime = MacroRegime.BEAR_TREND
        score = -80.0

    return RegimeResult(
        macro_regime=regime,
        ema50=ema,
        close_4h=close,
        score=score,
        adx=10.0 + (int(close) % 30),
        atr_percentile=50.0,
    )
