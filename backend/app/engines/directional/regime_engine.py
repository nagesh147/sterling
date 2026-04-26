import numpy as np
from typing import List
from app.schemas.market import Candle
from app.schemas.directional import RegimeResult, MacroRegime
from app.engines.indicators.ema import compute_ema


def compute_regime(candles_4h: List[Candle], ema_period: int = 50) -> RegimeResult:
    if not candles_4h:
        return RegimeResult(
            macro_regime=MacroRegime.NEUTRAL,
            ema50=0.0,
            close_4h=0.0,
            score=0.0,
        )

    closes = np.array([c.close for c in candles_4h], dtype=np.float64)
    ema = compute_ema(closes, ema_period)
    current_close = closes[-1]
    current_ema = ema[-1]

    if current_ema == 0.0:
        regime = MacroRegime.NEUTRAL
        score = 50.0
    elif current_close > current_ema:
        regime = MacroRegime.BULLISH
        pct_above = (current_close - current_ema) / current_ema * 100
        score = min(100.0, 50.0 + pct_above * 5)
    else:
        regime = MacroRegime.BEARISH
        pct_below = (current_ema - current_close) / current_ema * 100
        score = max(0.0, 50.0 - pct_below * 5)

    return RegimeResult(
        macro_regime=regime,
        ema50=float(current_ema),
        close_4h=float(current_close),
        score=round(score, 2),
    )
