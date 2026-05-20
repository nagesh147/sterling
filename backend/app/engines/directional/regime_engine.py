import os
import numpy as np
from typing import List, Literal, Optional, Dict, Any
from app.schemas.market import Candle
from app.engines.directional.regime_hmm import RegimeHMMModel
from app.schemas.directional import RegimeResult, MacroRegime
from app.engines.indicators.ema import compute_ema, ema_dual
from app.engines.indicators.atr import compute_atr
from app.engines.indicators.adx import adx as compute_adx_arr


# Issue 3 — IDLE strictness profile.
# "strict" (legacy):  pct < 30 on 2 consecutive bars OR (slope<0 AND pct<35).
# "loose":            pct < 25 on 2 consecutive bars OR (slope<0 AND pct<30).
# The default reads from the STERLING_IDLE_STRICTNESS env var; callers can
# override per-call via the `idle_strictness` kwarg below.
_DEFAULT_IDLE_STRICTNESS: Literal["strict", "loose"] = (
    "loose" if os.environ.get("STERLING_IDLE_STRICTNESS", "").lower() == "loose"
    else "strict"
)


def _atr_pct_at(atr_arr: np.ndarray, pos: int, lookback: int = 100) -> float:
    """ATR percentile for a specific position in the array."""
    start = max(0, pos - lookback + 1)
    recent = atr_arr[start:pos + 1]
    valid = recent[~np.isnan(recent)]
    if len(valid) < 5 or np.isnan(atr_arr[pos]):
        return 50.0
    return float(np.sum(atr_arr[pos] > valid) / len(valid) * 100)


# Tier A #6 — HTF momentum z-score constants.
_MOMENTUM_Z_LOOKBACK = 50
_MOMENTUM_Z_THRESHOLD = 0.5
_MOMENTUM_Z_BONUS = 2.0


def _momentum_z(closes: np.ndarray, pos: int, lookback: int = _MOMENTUM_Z_LOOKBACK) -> Optional[float]:
    """50-bar rolling momentum Z-score: (close - mean) / std on the last `lookback` closes.
    Returns None until `lookback` bars are available or std is zero."""
    if pos + 1 < lookback:
        return None
    window = closes[pos + 1 - lookback: pos + 1]
    if window.size < lookback:
        return None
    mean = float(np.mean(window))
    std = float(np.std(window, ddof=0))
    if std <= 1e-12:
        return None
    return float((window[-1] - mean) / std)


def _atr_slope(atr_arr: np.ndarray, closes: np.ndarray, pos: int) -> float:
    """
    Normalized ATR slope: Δ(ATR/Close) between current and previous bar.
    Negative = ATR contracting relative to price (volatility drying up).
    """
    if pos < 1 or np.isnan(atr_arr[pos]) or np.isnan(atr_arr[pos - 1]):
        return 0.0
    if closes[pos] <= 0 or closes[pos - 1] <= 0:
        return 0.0
    cur = atr_arr[pos] / closes[pos]
    prev = atr_arr[pos - 1] / closes[pos - 1]
    return round(cur - prev, 6)


def compute_regime(
    candles_4h: List[Candle],
    ema_period: int = 50,
    macro_filter: str = "adx_4h",
    *,
    idle_strictness: Literal["strict", "loose", "auto"] = "auto",
    hmm_prediction: Optional[Dict[str, Any]] = None,
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
    cur_atr_slope = _atr_slope(atr_arr, closes, n - 1)
    cur_momentum_z = _momentum_z(closes, n - 1)

    # IDLE detection — strict (legacy) vs loose (Issue 3) thresholds.
    # strict:  pct<30 on 2 consecutive bars OR (slope<0 AND pct<35)
    # loose:   pct<25 on 2 consecutive bars OR (slope<0 AND pct<30)
    strictness = idle_strictness
    if strictness == "auto":
        strictness = _DEFAULT_IDLE_STRICTNESS
    if strictness == "loose":
        pct_thr_low = 25
        slope_pct_thr = 30
    else:
        pct_thr_low = 30
        slope_pct_thr = 35
    pct_low_now  = _atr_pct_at(atr_arr, n - 1, 100) < pct_thr_low
    pct_low_prev = n >= 2 and _atr_pct_at(atr_arr, n - 2, 100) < pct_thr_low
    slope_contraction = cur_atr_slope < 0 and cur_atr_pct < slope_pct_thr
    cooldown_active = (pct_low_now and pct_low_prev) or slope_contraction

    # Parse HMM prediction if provided by the orchestrator
    hmm_regime = hmm_prediction.get("regime") if hmm_prediction else None
    hmm_conf = hmm_prediction.get("confidence") if hmm_prediction else None

    _common = dict(
        atr_percentile=round(cur_atr_pct, 2),
        adx=round(cur_adx, 4),
        ema21=round(cur_ema21, 4),
        ema55=round(cur_ema55, 4),
        atr_slope=round(cur_atr_slope, 6),
        momentum_z=(round(cur_momentum_z, 4) if cur_momentum_z is not None else None),
        hmm_primary_regime=hmm_regime,
        hmm_confidence=hmm_conf,
    )

    if cur_ema21 == 0.0 or cur_ema55 == 0.0:
        return RegimeResult(
            macro_regime=MacroRegime.NEUTRAL,
            ema50=cur_ema21, close_4h=cur_close, score=0.0,
            **_common,
        )

    # Scalping mode: simple direction without ADX/cooldown gates
    if macro_filter == "off":
        regime = MacroRegime.BULL_TREND if cur_close > cur_ema21 else MacroRegime.BEAR_TREND
        adx_c = min(cur_adx / 40.0, 1.0) * 12
        atr_c = min(cur_atr_pct / 80.0, 1.0) * 8
        score = round(adx_c + atr_c, 2)
        res = RegimeResult(
            macro_regime=regime,
            ema50=cur_ema21, close_4h=cur_close, score=score,
            **_common,
        )
        if len(_REGIME_CACHE) > 50000:
            _REGIME_CACHE.clear()
        _REGIME_CACHE[cache_key] = res
        return res

    # ADX thresholds: crypto markets trend at lower ADX than FX/equities.
    # Strong trend: ADX >= 20 (was 25 — too strict, blocked most crypto signals)
    # Moderate trend: ADX >= 15 → RANGING (allow partial signals via setup_engine)
    ADX_TREND = 20
    strict = _DEFAULT_IDLE_STRICTNESS
    if idle_strictness != "auto":
        strict = idle_strictness

    is_idle = False
    if n >= 2:
        prev_atr_pct = _atr_pct_at(atr_arr, n - 2, 100)
        if strict == "strict":
            consec = (cur_atr_pct < 30.0 and prev_atr_pct < 30.0)
            slope_rule = (cur_atr_slope < 0.0 and cur_atr_pct < 35.0)
            is_idle = consec or slope_rule
        else:
            consec = (cur_atr_pct < 25.0 and prev_atr_pct < 25.0)
            slope_rule = (cur_atr_slope < 0.0 and cur_atr_pct < 30.0)
            is_idle = consec or slope_rule

    # Base common metrics
    _common = {
        "ema21": cur_ema21,
        "ema55": cur_ema55,
        "adx": cur_adx,
        "atr_pct": cur_atr_pct,
        "atr_slope": cur_atr_slope,
        "momentum_z": cur_momentum_z,
        "hmm_primary_regime": hmm_prediction.get("regime") if hmm_prediction else None,
        "hmm_confidence": hmm_prediction.get("confidence") if hmm_prediction else None,
    }

    # HMM override integration if supplied and enabled via env
    if hmm_prediction and os.environ.get("STERLING_HMM_ENABLED", "true").lower() == "true":
        pred_state = hmm_prediction.get("predicted_state")
        conf = hmm_prediction.get("confidence", 0.0)
        # If model outputs 2, it is high-vol/trend. If 0 or 1, it's low-vol/ranging/idle.
        # Force IDLE if HMM is very confident (e.g. >80%) about a low-vol regime.
        if pred_state in [0, 1] and conf > 0.80:
            is_idle = True

    # 1. Macro Filter Veto check (Tier B #12)
    # If macro_filter is 'adx_4h' and ADX is under 20, force NEUTRAL (fully sidelined).
    adx_veto = False
    if macro_filter == "adx_4h":
        # Check if HMM is active and overrides the ADX veto
        hmm_override = (
            hmm_prediction and
            hmm_prediction.get("predicted_state") == 2
            and hmm_prediction.get("confidence", 0.0) > 0.70
        )
        if cur_adx < 20.0 and not hmm_override:
            adx_veto = True

    # 2. Strict IDLE Regime Assignment
    ADX_WEAK = 15
    if is_idle:
        regime = MacroRegime.IDLE
        score = 0.0
    elif adx_veto:
        regime = MacroRegime.NEUTRAL
        score = 0.0
    elif cur_ema21 > cur_ema55 and cur_close > cur_ema21 and cur_adx >= ADX_WEAK:
        regime = MacroRegime.BULL_TREND
        adx_component = min(cur_adx / 40.0, 1.0) * 12
        atr_component = min(cur_atr_pct / 80.0, 1.0) * 8
        mom_bonus = (
            _MOMENTUM_Z_BONUS
            if cur_momentum_z is not None and cur_momentum_z > _MOMENTUM_Z_THRESHOLD
            else 0.0
        )
        score = round(adx_component + atr_component + mom_bonus, 2)
    elif cur_ema21 < cur_ema55 and cur_close < cur_ema21 and cur_adx >= ADX_WEAK:
        regime = MacroRegime.BEAR_TREND
        adx_component = min(cur_adx / 40.0, 1.0) * 12
        atr_component = min(cur_atr_pct / 80.0, 1.0) * 8
        mom_bonus = (
            _MOMENTUM_Z_BONUS
            if cur_momentum_z is not None and cur_momentum_z < -_MOMENTUM_Z_THRESHOLD
            else 0.0
        )
        score = round(adx_component + atr_component + mom_bonus, 2)
    else:
        regime = MacroRegime.RANGING
        score = 0.0

    res = RegimeResult(
        macro_regime=regime,
        ema50=cur_ema21,
        close_4h=cur_close,
        score=score,
        atr_percentile=round(cur_atr_pct, 2),
        **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in _common.items() if v is not None and k != "atr_pct"}
    )

    if len(_REGIME_CACHE) > 50000:
        _REGIME_CACHE.clear()
    _REGIME_CACHE[cache_key] = res
    return res
