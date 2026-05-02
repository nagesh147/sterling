import numpy as np
from typing import List
from app.schemas.market import Candle
from app.schemas.directional import RegimeResult, MacroRegime
from app.engines.indicators.ema import compute_ema
from app.engines.indicators.adx import calc_adx

_MACRO_SCORES = {
    MacroRegime.BULL_TRENDING: 100.0,
    MacroRegime.BULLISH: 75.0,
    MacroRegime.BULL_WEAK: 60.0,
    MacroRegime.BULL_RANGING: 40.0,
    MacroRegime.NEUTRAL: 50.0,
    MacroRegime.CHOPPY: 0.0,
    MacroRegime.BEAR_RANGING: 40.0,
    MacroRegime.BEAR_WEAK: 60.0,
    MacroRegime.BEARISH: 75.0,
    MacroRegime.BEAR_TRENDING: 100.0,
}


def _count_ema_crosses(candles: List[Candle], ema: List[float]) -> int:
    crosses = 0
    for i in range(1, len(candles)):
        prev_above = candles[i - 1].close > ema[i - 1]
        curr_above = candles[i].close > ema[i]
        if prev_above != curr_above:
            crosses += 1
    return crosses


def compute_regime(
    candles_4h: List[Candle],
    ema_period: int = 50,
    macro_filter: str = "adx_4h",
) -> RegimeResult:
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
        return RegimeResult(
            macro_regime=MacroRegime.NEUTRAL,
            ema50=float(current_ema),
            close_4h=float(current_close),
            score=50.0,
        )

    if macro_filter == "off":
        # scalping mode — simple EMA filter
        regime = MacroRegime.BULL_TRENDING if current_close > current_ema else MacroRegime.BEAR_TRENDING
        score = _MACRO_SCORES[regime]
        return RegimeResult(
            macro_regime=regime,
            ema50=float(current_ema),
            close_4h=float(current_close),
            score=round(score, 2),
        )

    adx_vals = calc_adx(candles_4h, 14)
    current_adx = next((v for v in reversed(adx_vals) if v is not None), None)

    ema_list = ema.tolist()
    ema50_slope = (ema[-1] - ema[-5]) / ema[-5] if len(ema) >= 5 and ema[-5] > 0 else 0.0
    recent_candles = candles_4h[-20:]
    recent_ema = ema_list[-20:]
    crosses = _count_ema_crosses(recent_candles, recent_ema)

    adx_v = current_adx if current_adx is not None else 0.0

    if current_close > current_ema:
        if adx_v > 20 and ema50_slope > 0.0005 and crosses < 3:
            regime = MacroRegime.BULL_TRENDING
        elif adx_v < 20:
            regime = MacroRegime.BULL_RANGING
        elif crosses >= 3:
            regime = MacroRegime.CHOPPY
        else:
            regime = MacroRegime.BULL_WEAK
    else:
        if adx_v > 20 and ema50_slope < -0.0005 and crosses < 3:
            regime = MacroRegime.BEAR_TRENDING
        elif adx_v < 20:
            regime = MacroRegime.BEAR_RANGING
        else:
            regime = MacroRegime.BEAR_WEAK

    score = _MACRO_SCORES.get(regime, 50.0)
    return RegimeResult(
        macro_regime=regime,
        ema50=float(current_ema),
        close_4h=float(current_close),
        score=round(score, 2),
    )
