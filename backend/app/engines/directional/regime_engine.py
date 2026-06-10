"""Directional 4H regime engine — real ADX + SMA-slope classification.

Replaces the strategy-reset stub (EMA5 cross + fabricated `adx = 10 +
int(close)%30`) with the validated regime read: ADX(14) for trend strength,
SMA(50) slope for direction → BULL_TREND / BEAR_TREND / RANGING. The signed
`score` scales with real ADX strength, so it means something.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from app.schemas.market import Candle
from app.schemas.directional import RegimeResult, MacroRegime
from app.engines.directional.indicators import candles_to_df, adx14, sma_slope

_REGIME_CACHE: dict = {}

_ADX_TREND = 25.0
_MIN_BARS = 50


def compute_regime(
    candles_4h: List[Candle],
    ema_period: int = 50,
    macro_filter: str = "adx_4h",
    *,
    idle_strictness: Literal["strict", "loose", "auto"] = "auto",
    hmm_prediction: Optional[Dict[str, Any]] = None,
) -> RegimeResult:
    """ADX(14) + SMA(50)-slope regime. IDLE until enough history accrues."""
    if not candles_4h:
        return RegimeResult(macro_regime=MacroRegime.IDLE, ema50=0.0,
                            close_4h=0.0, score=0.0)
    df = candles_to_df(candles_4h)
    close = float(df["close"].iloc[-1])
    if len(df) < _MIN_BARS:
        return RegimeResult(macro_regime=MacroRegime.IDLE, ema50=close,
                            close_4h=close, score=0.0)

    adx = float(adx14(df).iloc[-1])
    slope = sma_slope(df["close"], window=ema_period, lookback=5)
    sma50 = float(df["close"].rolling(ema_period).mean().iloc[-1])
    mag = min(100.0, adx * 2.5)                # ADX 40 -> 100, ADX 25 -> 62.5

    if adx >= _ADX_TREND and slope > 0:
        regime, score = MacroRegime.BULL_TREND, mag
    elif adx >= _ADX_TREND and slope < 0:
        regime, score = MacroRegime.BEAR_TREND, -mag
    else:
        regime, score = MacroRegime.RANGING, 0.0

    return RegimeResult(
        macro_regime=regime,
        ema50=round(sma50, 2),
        close_4h=close,
        score=round(score, 1),
        adx=round(adx, 1),
        atr_percentile=50.0,
    )
