import numpy as np
from typing import List
from app.schemas.market import Candle
from app.schemas.directional import RegimeResult, MacroRegime
from app.engines.indicators.ema import compute_ema, ema_dual
from app.engines.indicators.atr import compute_atr
from app.engines.indicators.adx import adx as compute_adx_arr


def _atr_pct_at(atr_arr: np.ndarray, pos: int, lookback: int = 100) -> float:
    """ATR percentile for a specific position in the array."""
    start = max(0, pos - lookback + 1)
    recent = atr_arr[start:pos + 1]
    valid = recent[~np.isnan(recent)]
    if len(valid) < 5 or np.isnan(atr_arr[pos]):
        return 50.0
    return float(np.sum(atr_arr[pos] > valid) / len(valid) * 100)


def compute_regime(
    candles_4h: List[Candle],
    ema_period: int = 50,
    macro_filter: str = "adx_4h",
) -> RegimeResult:
    if not candles_4h:
        return RegimeResult(
            macro_regime=MacroRegime.NEUTRAL,
            ema50=0.0, close_4h=0.0, score=0.0,
        )

    highs = np.array([c.high for c in candles_4h], dtype=np.float64)
    lows = np.array([c.low for c in candles_4h], dtype=np.float64)
    closes = np.array([c.close for c in candles_4h], dtype=np.float64)

    ema21_arr, ema55_arr = ema_dual(closes, 21, 55)
    atr_arr = compute_atr(highs, lows, closes, 14)
    adx_arr = compute_adx_arr(highs, lows, closes, 14)

    n = len(closes)
    cur_close = float(closes[-1])
    cur_ema21 = float(ema21_arr[-1])
    cur_ema55 = float(ema55_arr[-1])
    cur_adx = float(adx_arr[-1])
    cur_atr_pct = _atr_pct_at(atr_arr, n - 1, 100)

    # Cooldown: IDLE only when current AND previous bar both have ATR pct < 30.
    # A single quiet bar used to pause the strategy for 4 bars — too aggressive.
    cooldown_active = (
        n >= 2
        and _atr_pct_at(atr_arr, n - 1, 100) < 30
        and _atr_pct_at(atr_arr, n - 2, 100) < 30
    )

    if cur_ema21 == 0.0 or cur_ema55 == 0.0:
        return RegimeResult(
            macro_regime=MacroRegime.NEUTRAL,
            ema50=cur_ema21, close_4h=cur_close, score=0.0,
            atr_percentile=round(cur_atr_pct, 2),
            adx=round(cur_adx, 4),
            ema21=round(cur_ema21, 4),
            ema55=round(cur_ema55, 4),
        )

    # Scalping mode: simple direction without ADX/cooldown gates
    if macro_filter == "off":
        regime = MacroRegime.BULL_TREND if cur_close > cur_ema21 else MacroRegime.BEAR_TREND
        adx_c = min(cur_adx / 40.0, 1.0) * 12
        atr_c = min(cur_atr_pct / 80.0, 1.0) * 8
        score = round(adx_c + atr_c, 2)
        return RegimeResult(
            macro_regime=regime,
            ema50=cur_ema21, close_4h=cur_close, score=score,
            atr_percentile=round(cur_atr_pct, 2),
            adx=round(cur_adx, 4),
            ema21=round(cur_ema21, 4),
            ema55=round(cur_ema55, 4),
        )

    # ADX thresholds: crypto markets trend at lower ADX than FX/equities.
    # Strong trend: ADX >= 20 (was 25 — too strict, blocked most crypto signals)
    # Moderate trend: ADX >= 15 → RANGING (allow partial signals via setup_engine)
    ADX_TREND = 20
    ADX_WEAK  = 15

    if cooldown_active:
        regime = MacroRegime.IDLE
        score = 0.0
    elif cur_atr_pct > 65 and cur_adx < ADX_TREND:
        regime = MacroRegime.VOLATILE
        score = 8.0
    elif cur_adx < ADX_WEAK:
        regime = MacroRegime.RANGING
        score = 0.0
    elif cur_ema21 > cur_ema55 and cur_close > cur_ema21 and cur_adx >= ADX_WEAK:
        regime = MacroRegime.BULL_TREND
        adx_component = min(cur_adx / 40.0, 1.0) * 12
        atr_component = min(cur_atr_pct / 80.0, 1.0) * 8
        score = round(adx_component + atr_component, 2)
    elif cur_ema21 < cur_ema55 and cur_close < cur_ema21 and cur_adx >= ADX_WEAK:
        regime = MacroRegime.BEAR_TREND
        adx_component = min(cur_adx / 40.0, 1.0) * 12
        atr_component = min(cur_atr_pct / 80.0, 1.0) * 8
        score = round(adx_component + atr_component, 2)
    else:
        regime = MacroRegime.RANGING
        score = 0.0

    return RegimeResult(
        macro_regime=regime,
        ema50=cur_ema21,          # kept for backward compat
        close_4h=cur_close,
        score=score,
        atr_percentile=round(cur_atr_pct, 2),
        adx=round(cur_adx, 4),
        ema21=round(cur_ema21, 4),
        ema55=round(cur_ema55, 4),
    )
