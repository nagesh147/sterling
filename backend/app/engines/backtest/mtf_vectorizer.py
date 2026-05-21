"""
W11 — Vectorized indicator + regime/signal pre-computation for fast MTF
backtests.

The legacy `_replay_profile` loop called `compute_regime(candles_regime[:k])`
and `compute_signal(candles_signal[max(0,i-200):i+1])` per signal bar, which
turned an O(N) backtest into O(N²). For CPCV / walk-forward / heavy sweeps
the per-bar recompute dominates wall-clock.

This module:

  1. Converts the signal and regime candle lists to Pandas DataFrames.
  2. Computes all indicator series (ATR, ADX, RSI, BB, KC, Heikin-Ashi,
     Supertrend ×3, VWAP-per-session, rolling volume median, ATR percentile
     rank) once over the full series using `.rolling()` / `.ewm()` /
     `.shift()` + the existing numpy helpers — all O(N).
  3. Derives one `RegimeResult` per regime bar and one `SignalResult` per
     signal bar from those arrays.
  4. Maps each signal bar to the index of the most-recently-closed regime
     bar so the backtest loop replaces `compute_regime/compute_signal` calls
     with O(1) array lookups.

The result is `O(N_signal + N_regime)` total instead of `O(N²)`. The output
mirrors the live engines' semantics but is allowed to differ in the early
warmup window because Supertrend and ATR run over the full series (more
context, identical state once converged).

Pure module: no DB, no I/O, no `time.time()`.
"""
from __future__ import annotations
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.schemas.market import Candle
from app.schemas.directional import (
    MacroRegime, RegimeResult, SignalResult,
)
from app.engines.indicators.atr import compute_atr
from app.engines.indicators.adx import adx as compute_adx
from app.engines.indicators.ema import compute_ema, ema_dual
from app.engines.indicators.heikin_ashi import compute_heikin_ashi, ha_body_bull
from app.engines.indicators.rsi import rsi as compute_rsi
from app.engines.indicators.supertrend import compute_supertrend
from app.engines.indicators.smc import compute_smc


# Mirrors regime_engine.compute_regime crypto-tuned thresholds.
_ADX_TREND = 20
_ADX_WEAK = 15

# Tier A #6 — HTF momentum z-score constants (mirror regime_engine).
_MOMENTUM_Z_LOOKBACK = 50
_MOMENTUM_Z_THRESHOLD = 0.5
_MOMENTUM_Z_BONUS = 2.0

# v4 — Confluence weights / thresholds are imported from the single source
# of truth in signal_weights. Pre-v4 this module had its own copy that
# diverged from signal_engine's copy; baselines and live computed different
# scores from the same data. Now both call sites share the same constants.
from app.engines.directional.signal_weights import (
    V4_BASE_WEIGHTS as _SIG_WEIGHTS,
    V4_TOTAL_WEIGHT as _SIG_TOTAL_WEIGHT,
    V4_CVD_WINDOW as _CVD_WINDOW,
    V4_CVD_DIVERGENCE_PENALTY as _CVD_DIVERGENCE_PENALTY,
    V4_CVD_DIVERGENCE_RATIO as _CVD_DIVERGENCE_RATIO,
    V4_RSI_LONG_LO, V4_RSI_LONG_HI,
    V4_RSI_SHORT_LO, V4_RSI_SHORT_HI,
    V4_RSI_LONG_MOM_LO, V4_RSI_LONG_MOM_HI,
    V4_RSI_SHORT_MOM_LO, V4_RSI_SHORT_MOM_HI,
    V4_VOL_SPIKE_MULT,
    V4_BB_PERIOD, V4_BB_STD,
    V4_KC_PERIOD, V4_KC_ATR_PERIOD, V4_KC_MULT,
    V4_HA_REAL_DIV_PCT,
    V4_STRENGTH_STRONG_PCT, V4_STRENGTH_SIGNAL_PCT,
    V4_STALENESS_LOOKBACK,
    regime_aware_weights,
)

_MS_PER_DAY = 86_400_000


def _default_idle_strictness() -> str:
    """Match regime_engine._DEFAULT_IDLE_STRICTNESS — env-driven, default strict."""
    return (
        "loose"
        if os.environ.get("STERLING_IDLE_STRICTNESS", "").lower() == "loose"
        else "strict"
    )


@dataclass
class VectorizedReplay:
    """Precomputed per-bar regime / signal results aligned to the signal series."""
    n_signal: int
    n_regime: int
    # One `RegimeResult` per regime bar. Backtest indexes with `regime_idx-1`.
    regimes_per_regime_bar: List[RegimeResult]
    # One `SignalResult` per signal bar.
    signals: List[SignalResult]
    # For each signal bar, the count of regime bars whose CLOSE timestamp
    # has elapsed by the signal bar's open. Matches the legacy cursor
    # semantics so the backtest loop can drop the manual while-advance.
    regime_idx_at_signal: np.ndarray
    # ATR series exposed for stop / trail logic in the replay loop.
    signal_atr14: np.ndarray
    signal_atr22: np.ndarray
    regime_atr14: np.ndarray
    # v4 Phase 1 — Per-bar mean-reversion SignalResult (fade-extremes track).
    # Populated when `track="mean_reversion"` is supplied to vectorize_replay;
    # else stays as the same trend-following signals (defensive default).
    mr_signals: Optional[List[SignalResult]] = None


# ── Candle → DataFrame helpers ────────────────────────────────────────────────


def _candles_to_df(candles: List[Candle]) -> pd.DataFrame:
    """Materialise a list of Candle objects into a tidy OHLCV DataFrame."""
    if not candles:
        return pd.DataFrame(
            columns=["timestamp_ms", "open", "high", "low", "close", "volume"],
            dtype=np.float64,
        )
    return pd.DataFrame(
        {
            "timestamp_ms": np.array([c.timestamp_ms for c in candles], dtype=np.int64),
            "open":         np.array([c.open  for c in candles], dtype=np.float64),
            "high":         np.array([c.high  for c in candles], dtype=np.float64),
            "low":          np.array([c.low   for c in candles], dtype=np.float64),
            "close":        np.array([c.close for c in candles], dtype=np.float64),
            "volume":       np.array([c.volume for c in candles], dtype=np.float64),
        }
    )


def _rolling_atr_percentile(atr: np.ndarray, lookback: int = 100) -> np.ndarray:
    """
    Replicates regime_engine._atr_pct_at across the whole array.

    For each position k:
      percentile = sum(atr[k] > valid_window) / len(valid_window) * 100,
      with valid_window = atr[max(0, k-lookback+1):k+1] minus NaNs.
      Falls back to 50.0 when fewer than 5 valid samples in the window.

    Implemented as a single Python loop over numpy slices — bounded inner
    work (lookback ≤ 100) keeps this O(N·100) ≈ O(N) in practice.
    """
    n = len(atr)
    out = np.full(n, 50.0, dtype=np.float64)
    for k in range(n):
        start = max(0, k - lookback + 1)
        window = atr[start:k + 1]
        valid = window[~np.isnan(window)]
        if len(valid) < 5 or np.isnan(atr[k]):
            out[k] = 50.0
        else:
            out[k] = float(np.sum(atr[k] > valid) / len(valid) * 100)
    return out


def _vwap_per_session(df: pd.DataFrame) -> np.ndarray:
    """Cumulative VWAP per UTC calendar day (matches signal_engine._to_vwap_candles)."""
    if df.empty:
        return np.array([], dtype=np.float64)
    day_key = (df["timestamp_ms"].values // _MS_PER_DAY).astype(np.int64)
    typical = (df["high"].values + df["low"].values + df["close"].values) / 3.0
    pv = typical * df["volume"].values
    df_local = pd.DataFrame(
        {"day": day_key, "pv": pv, "vol": df["volume"].values}
    )
    grouped = df_local.groupby("day", sort=False)
    cum_pv = grouped["pv"].cumsum().values
    cum_vol = grouped["vol"].cumsum().values
    vwap = np.where(cum_vol > 0, cum_pv / np.where(cum_vol > 0, cum_vol, 1.0),
                    df["close"].values)
    return vwap


def map_regime_idx_to_signal(
    signal_ts: np.ndarray, regime_ts: np.ndarray, regime_bar_ms: int,
) -> np.ndarray:
    """
    For each signal bar timestamp, return the number of regime bars whose
    close has occurred by that timestamp.

    Matches the legacy monotonic cursor:
        while regime_ts[regime_idx] + regime_bar_ms <= ts: regime_idx += 1

    Implemented with `np.searchsorted` for O(N_signal · log N_regime) — for
    realistic N this is effectively O(N).
    """
    if regime_ts.size == 0:
        return np.zeros(signal_ts.size, dtype=np.int64)
    reg_close_ts = regime_ts + regime_bar_ms
    # `side='right'` so a signal whose ts equals the regime-close ts sees that
    # bar as already closed — identical to the `<= ts` legacy condition.
    return np.searchsorted(reg_close_ts, signal_ts, side="right").astype(np.int64)


# ── Regime vectoriser ─────────────────────────────────────────────────────────


def build_regimes_full(
    candles_regime: List[Candle],
    *,
    idle_strictness: str = "auto",
) -> Tuple[List[RegimeResult], np.ndarray]:
    """
    Vectorised regime computation — one RegimeResult per regime bar plus
    the ATR(14) array used downstream by the replay loop.

    Mirrors `regime_engine.compute_regime`'s default (`macro_filter='adx_4h'`)
    branch, including the IDLE cooldown logic. Scalping-mode `macro_filter='off'`
    is not used by the backtest, so it is intentionally not replicated here.
    """
    df = _candles_to_df(candles_regime)
    n = len(df)
    if n == 0:
        return [], np.array([], dtype=np.float64)

    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    ema21, ema55 = ema_dual(closes, 21, 55)
    atr14 = compute_atr(highs, lows, closes, 14)
    adx14 = compute_adx(highs, lows, closes, 14)
    atr_pct = _rolling_atr_percentile(atr14, lookback=100)

    # Tier A #6 — vectorised 50-bar momentum z-score on regime-TF close.
    s_reg_close = pd.Series(closes)
    mom_mean = s_reg_close.rolling(_MOMENTUM_Z_LOOKBACK, min_periods=_MOMENTUM_Z_LOOKBACK).mean()
    mom_std = s_reg_close.rolling(_MOMENTUM_Z_LOOKBACK, min_periods=_MOMENTUM_Z_LOOKBACK).std(ddof=0)
    # Where std is zero or NaN we treat momentum_z as undefined (None at emit time).
    with np.errstate(invalid="ignore", divide="ignore"):
        momentum_z_arr = ((s_reg_close - mom_mean) / mom_std.where(mom_std > 1e-12)).values

    # Normalised ATR slope: Δ(ATR / Close) — vectorised via .shift().
    s_close = pd.Series(closes)
    s_atr = pd.Series(atr14)
    atr_norm = (s_atr / s_close.where(s_close > 0)).fillna(0.0)
    atr_slope = (atr_norm - atr_norm.shift(1)).fillna(0.0).round(6).values

    strictness = idle_strictness
    if strictness == "auto":
        strictness = _default_idle_strictness()
    if strictness == "loose":
        pct_thr_low, slope_pct_thr = 25, 30
    else:
        pct_thr_low, slope_pct_thr = 30, 35

    pct_low_now = atr_pct < pct_thr_low
    pct_low_prev = np.concatenate([[False], pct_low_now[:-1]])
    slope_contraction = (atr_slope < 0) & (atr_pct < slope_pct_thr)
    cooldown = (pct_low_now & pct_low_prev) | slope_contraction

    out: List[RegimeResult] = []
    for k in range(n):
        cur_close = float(closes[k])
        cur_ema21 = float(ema21[k])
        cur_ema55 = float(ema55[k])
        cur_adx = float(adx14[k])
        cur_atr_pct = float(atr_pct[k])
        cur_atr_slope = float(atr_slope[k])

        cur_mom_z_raw = momentum_z_arr[k]
        cur_mom_z = (
            float(cur_mom_z_raw)
            if cur_mom_z_raw is not None and not np.isnan(cur_mom_z_raw)
            else None
        )
        common = dict(
            atr_percentile=round(cur_atr_pct, 2),
            adx=round(cur_adx, 4),
            ema21=round(cur_ema21, 4),
            ema55=round(cur_ema55, 4),
            atr_slope=round(cur_atr_slope, 6),
            momentum_z=(round(cur_mom_z, 4) if cur_mom_z is not None else None),
        )

        if cur_ema21 == 0.0 or cur_ema55 == 0.0:
            out.append(RegimeResult(
                macro_regime=MacroRegime.NEUTRAL,
                ema50=cur_ema21, close_4h=cur_close, score=0.0,
                **common,
            ))
            continue

        if cooldown[k]:
            regime, score = MacroRegime.IDLE, 0.0
        elif cur_atr_pct > 65 and cur_adx < _ADX_TREND:
            regime, score = MacroRegime.VOLATILE, 8.0
        elif cur_adx < _ADX_WEAK:
            regime, score = MacroRegime.RANGING, 0.0
        elif cur_ema21 > cur_ema55 and cur_close > cur_ema21 and cur_adx >= _ADX_WEAK:
            regime = MacroRegime.BULL_TREND
            adx_c = min(cur_adx / 40.0, 1.0) * 12
            atr_c = min(cur_atr_pct / 80.0, 1.0) * 8
            mom_bonus = (
                _MOMENTUM_Z_BONUS
                if cur_mom_z is not None and cur_mom_z > _MOMENTUM_Z_THRESHOLD
                else 0.0
            )
            score = round(adx_c + atr_c + mom_bonus, 2)
        elif cur_ema21 < cur_ema55 and cur_close < cur_ema21 and cur_adx >= _ADX_WEAK:
            regime = MacroRegime.BEAR_TREND
            adx_c = min(cur_adx / 40.0, 1.0) * 12
            atr_c = min(cur_atr_pct / 80.0, 1.0) * 8
            mom_bonus = (
                _MOMENTUM_Z_BONUS
                if cur_mom_z is not None and cur_mom_z < -_MOMENTUM_Z_THRESHOLD
                else 0.0
            )
            score = round(adx_c + atr_c + mom_bonus, 2)
        else:
            regime, score = MacroRegime.RANGING, 0.0

        out.append(RegimeResult(
            macro_regime=regime,
            ema50=cur_ema21,  # back-compat name
            close_4h=cur_close,
            score=score,
            **common,
        ))
    return out, atr14


# ── Signal vectoriser ─────────────────────────────────────────────────────────


def _staleness_lookback(
    trend: np.ndarray,
    st1_t: np.ndarray, st2_t: np.ndarray, st3_t: np.ndarray,
    st_threshold: int,
) -> np.ndarray:
    """
    Mirrors signal_engine.compute_signal's bars-since-flip lookback.

    For each bar i, walks back up to 15 prior bars and counts consecutive
    bars whose ST trend count >= threshold in the same direction. Returns
    a flag value of 16 when ALL looked-back bars matched (the for-else
    branch of the legacy implementation).
    """
    n = len(trend)
    out = np.zeros(n, dtype=np.int64)
    for i in range(n):
        d = int(trend[i])
        if d == 0:
            continue
        cnt = 0
        completed = True
        # Walk back at most 15 bars (j = i-1 .. max(0, i-15)).
        for j in range(i - 1, i - 16, -1):
            if j < 0:
                # Legacy stops the range at max(-1, n_arr - 17); the for-else
                # still fires when the range exhausts naturally, so completing
                # all available prior bars still triggers the flag.
                break
            gc_prev = (
                int(st1_t[j] == d) + int(st2_t[j] == d) + int(st3_t[j] == d)
            )
            if gc_prev >= st_threshold:
                cnt += 1
            else:
                completed = False
                break
        out[i] = 16 if completed else cnt
    return out


def build_signals_full(
    candles_signal: List[Candle],
    *,
    st_configs: Optional[List[Tuple[int, float]]] = None,
    st_threshold: int = 3,
    regime_labels: Optional[np.ndarray] = None,
) -> Tuple[List[SignalResult], np.ndarray, np.ndarray]:
    """
    Vectorised signal computation — one SignalResult per signal bar plus the
    ATR(14) and ATR(22) arrays used by the replay loop's stop / trail logic.

    Mirrors `signal_engine.compute_signal` but every indicator runs once over
    the full series via Pandas .rolling() / .ewm() / .shift() and the existing
    numpy helpers. The early warmup window (≲ 30 bars) returns a degenerate
    SignalResult to match the legacy short-circuit.

    When `regime_labels` is supplied (one label per signal bar, e.g. from
    `vectorize_replay`'s regime_idx_at_signal mapping), each bar's flag
    weights are scaled by the v4 regime profile. Trending bars favour
    st_flip + ha_aligned; volatile bars favour squeeze + volume; ranging
    bars favour rsi + rsi_momentum. See `signal_weights.V4_REGIME_PROFILES`.
    """
    df = _candles_to_df(candles_signal)
    n = len(df)
    cfgs = st_configs if st_configs is not None else [(7, 3.0), (14, 2.0), (21, 2.0)]
    if len(cfgs) != 3:
        raise ValueError(
            f"st_configs must have exactly 3 (period, multiplier) tuples, got {len(cfgs)}"
        )

    if n == 0:
        return [], np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    open_  = df["open"].values
    high   = df["high"].values
    low    = df["low"].values
    close  = df["close"].values
    volume = df["volume"].values

    atr14 = compute_atr(high, low, close, 14)
    atr22 = compute_atr(high, low, close, 22)

    rsi_arr = compute_rsi(close, 14)

    # Heikin-Ashi candles — sequential but already O(N).
    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(open_, high, low, close)
    ha_bull = ha_body_bull(open_, high, low, close)

    # Supertrend ×3 — already O(N).
    p1, m1 = cfgs[0]
    p2, m2 = cfgs[1]
    p3, m3 = cfgs[2]
    st1_line, st1_t = compute_supertrend(ha_h, ha_l, ha_c, p1, m1)
    st2_line, st2_t = compute_supertrend(high, low, close, p2, m2)

    vwap = _vwap_per_session(df)
    offset = vwap - close
    vwap_h = high + offset
    vwap_l = low + offset
    vwap_c = vwap
    st3_line, st3_t = compute_supertrend(vwap_h, vwap_l, vwap_c, p3, m3)

    # Bollinger Bands — .rolling() mean / std (sample, ddof=1).
    s_close = pd.Series(close)
    bb_mid = s_close.rolling(V4_BB_PERIOD, min_periods=V4_BB_PERIOD).mean()
    bb_std = s_close.rolling(V4_BB_PERIOD, min_periods=V4_BB_PERIOD).std(ddof=1)
    bb_hi_arr = (bb_mid + V4_BB_STD * bb_std).values
    bb_lo_arr = (bb_mid - V4_BB_STD * bb_std).values

    # Keltner Channels via EMA(period) ± mult · ATR(atr_period).
    kc_mid = compute_ema(close, V4_KC_PERIOD)
    kc_atr = compute_atr(high, low, close, V4_KC_ATR_PERIOD)
    kc_hi_arr = kc_mid + V4_KC_MULT * kc_atr
    kc_lo_arr = kc_mid - V4_KC_MULT * kc_atr

    # Volume median over rolling 20 bars — used for the 1.5× spike gate.
    vol_median = pd.Series(volume).rolling(20, min_periods=1).median().values

    # --- V4 SMC Vectorization ---
    smc_df = compute_smc(candles_signal)
    if not smc_df.empty and "CHOCH" in smc_df.columns and "BOS" in smc_df.columns:
        smc_signal = np.where(smc_df["CHOCH"] != 0, smc_df["CHOCH"], smc_df["BOS"])
        smc_trend_arr = pd.Series(smc_signal).replace(0, np.nan).ffill().fillna(0).values
    else:
        smc_trend_arr = np.zeros(n, dtype=np.int64)

    # ─ Vectorised flags ────────────────────────────────────────────────────
    green_count = (
        (st1_t == 1).astype(np.int64)
        + (st2_t == 1).astype(np.int64)
        + (st3_t == 1).astype(np.int64)
    )
    red_count = (
        (st1_t == -1).astype(np.int64)
        + (st2_t == -1).astype(np.int64)
        + (st3_t == -1).astype(np.int64)
    )

    all_green = green_count >= st_threshold
    all_red = red_count >= st_threshold

    prev_all_green = np.concatenate([[False], all_green[:-1]])
    prev_all_red = np.concatenate([[False], all_red[:-1]])
    green_arrow = all_green & ~prev_all_green
    red_arrow = all_red & ~prev_all_red

    trend = np.where(all_green, 1, np.where(all_red, -1, 0)).astype(np.int64)

    score_long = np.round(green_count / 3.0 * 100.0, 2)
    score_short = np.round(red_count / 3.0 * 100.0, 2)

    # BB+KC squeeze at i-1 (matches signal_engine `bb_lo[-2] > kc_lo[-2]`).
    bb_lo_prev = np.concatenate([[np.nan], bb_lo_arr[:-1]])
    bb_hi_prev = np.concatenate([[np.nan], bb_hi_arr[:-1]])
    kc_lo_prev = np.concatenate([[np.nan], kc_lo_arr[:-1]])
    kc_hi_prev = np.concatenate([[np.nan], kc_hi_arr[:-1]])
    with np.errstate(invalid="ignore"):
        squeezed = (bb_lo_prev > kc_lo_prev) & (bb_hi_prev < kc_hi_prev)
    breakout_long = close > bb_hi_arr
    breakout_short = close < bb_lo_arr
    squeeze_ok = squeezed & (breakout_long | breakout_short)

    # Volume spike: vol > V4_VOL_SPIKE_MULT × rolling-median volume.
    with np.errstate(invalid="ignore", divide="ignore"):
        vol_spike = (vol_median > 0) & (volume > V4_VOL_SPIKE_MULT * vol_median)

    # HA body alignment with trend.
    ha_aligned = np.where(
        trend == 1, ha_bull,
        np.where(trend == -1, ~ha_bull, False),
    ).astype(bool)

    # ST flip: direction-correct fresh arrow.
    st_flip = np.where(
        trend == 1, green_arrow,
        np.where(trend == -1, red_arrow, False),
    ).astype(bool)

    # HA / Real divergence filter.
    safe_close = np.where(close > 0, close, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        ha_real_div_pct = np.where(
            close > 0, np.abs(close - ha_c) / safe_close * 100.0, 0.0,
        )
    ha_real_div_pct = np.nan_to_num(ha_real_div_pct, nan=0.0)
    ha_real_aligned = ha_real_div_pct < V4_HA_REAL_DIV_PCT

    # RSI gates / momentum bonus — v4 thresholds (signal_weights.py).
    rsi_ok_long  = (rsi_arr > V4_RSI_LONG_LO)  & (rsi_arr < V4_RSI_LONG_HI)
    rsi_ok_short = (rsi_arr > V4_RSI_SHORT_LO) & (rsi_arr < V4_RSI_SHORT_HI)
    rsi_ok = np.where(
        trend == 1, rsi_ok_long,
        np.where(trend == -1, rsi_ok_short, False),
    ).astype(bool)
    rsi_momentum_long  = (rsi_arr > V4_RSI_LONG_MOM_LO)  & (rsi_arr < V4_RSI_LONG_MOM_HI)
    rsi_momentum_short = (rsi_arr > V4_RSI_SHORT_MOM_LO) & (rsi_arr < V4_RSI_SHORT_MOM_HI)
    rsi_momentum = np.where(
        trend == 1, rsi_momentum_long,
        np.where(trend == -1, rsi_momentum_short, False),
    ).astype(bool)

    # v4 — Regime-aware per-bar weight arrays. When `regime_labels` is None
    # all bars use V4_BASE_WEIGHTS; when supplied, each bar's weights are
    # scaled by the regime profile so trending bars favour st_flip + ha and
    # volatile bars favour squeeze + volume.
    flag_arrays = {
        "st_flip":         st_flip.astype(np.float64),
        "rsi":             rsi_ok.astype(np.float64),
        "rsi_momentum":    rsi_momentum.astype(np.float64),
        "squeeze":         squeeze_ok.astype(np.float64),
        "volume":          vol_spike.astype(np.float64),
        "ha_aligned":      ha_aligned.astype(np.float64),
        "ha_real_aligned": ha_real_aligned.astype(np.float64),
    }
    if regime_labels is None:
        # Static weights — fastest path.
        weight_arrays = {
            k: np.full(n, _SIG_WEIGHTS[k], dtype=np.float64)
            for k in _SIG_WEIGHTS
        }
    else:
        # Per-bar weights driven by regime label. At most ~8 unique labels in
        # a series so this stays O(N) with a small constant.
        weight_arrays = {
            k: np.full(n, _SIG_WEIGHTS[k], dtype=np.float64)
            for k in _SIG_WEIGHTS
        }
        labels_arr = np.asarray(regime_labels)
        for label in np.unique(labels_arr):
            if not label:
                continue
            mask = labels_arr == label
            if not mask.any():
                continue
            reg_w = regime_aware_weights(str(label))
            for k in _SIG_WEIGHTS:
                weight_arrays[k][mask] = reg_w[k]
    earned = sum(flag_arrays[k] * weight_arrays[k] for k in _SIG_WEIGHTS).astype(np.float64)
    total_weight_per_bar = sum(weight_arrays[k] for k in _SIG_WEIGHTS).astype(np.float64)

    bars_active = _staleness_lookback(trend, st1_t, st2_t, st3_t, st_threshold)
    stale_penalty = np.minimum(3, bars_active // 5)

    # Tier C #14 — vectorised CVD proxy and divergence penalty.
    tr = high - low
    safe_tr = np.where(tr > 0, tr, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        per_bar_delta = volume * ((close - open_) / safe_tr)
    per_bar_delta = np.nan_to_num(per_bar_delta, nan=0.0)
    per_bar_delta = np.clip(per_bar_delta, -np.abs(volume), np.abs(volume))
    s_delta = pd.Series(per_bar_delta)
    cvd_sum_arr = s_delta.rolling(_CVD_WINDOW, min_periods=1).sum().values
    abs_sum_arr = s_delta.abs().rolling(_CVD_WINDOW, min_periods=1).sum().values
    with np.errstate(invalid="ignore", divide="ignore"):
        cvd_ratio = np.where(
            abs_sum_arr > 0, np.abs(cvd_sum_arr) / abs_sum_arr, 0.0,
        )
    cvd_divergent = (
        (trend != 0)
        & (cvd_ratio > _CVD_DIVERGENCE_RATIO)
        & (
            ((trend == 1) & (cvd_sum_arr < 0))
            | ((trend == -1) & (cvd_sum_arr > 0))
        )
    )
    cvd_penalty = np.where(cvd_divergent, _CVD_DIVERGENCE_PENALTY, 0.0)

    earned_adj = np.maximum(0.0, earned - stale_penalty - cvd_penalty)
    # Per-bar total because regime-aware weights make the sum vary across bars.
    # Falls back to the static total when no regime_labels supplied (the
    # division divides by an array of all V4_TOTAL_WEIGHT, which is identical).
    pct = np.where(total_weight_per_bar > 0, earned_adj / total_weight_per_bar, 0.0)
    signal_score = np.round(pct * 20.0, 2)

    signal_strength = np.where(
        pct >= V4_STRENGTH_STRONG_PCT, "STRONG",
        np.where(pct >= V4_STRENGTH_SIGNAL_PCT, "SIGNAL", "NONE"),
    )

    # ─ Assemble SignalResult per bar ──────────────────────────────────────
    out: List[SignalResult] = []
    for i in range(n):
        if i < 30:
            # Match signal_engine.compute_signal's short-circuit for n < 30.
            out.append(SignalResult(
                trend=0, all_green=False, all_red=False,
                green_arrow=False, red_arrow=False,
                st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
                close_1h=float(close[i]),
                score_long=0.0, score_short=0.0,
                smc_trend=0,
            ))
            continue
        out.append(SignalResult(
            trend=int(trend[i]),
            all_green=bool(all_green[i]),
            all_red=bool(all_red[i]),
            green_arrow=bool(green_arrow[i]),
            red_arrow=bool(red_arrow[i]),
            st_trends=[int(st1_t[i]), int(st2_t[i]), int(st3_t[i])],
            st_values=[float(st1_line[i]), float(st2_line[i]), float(st3_line[i])],
            close_1h=float(close[i]),
            score_long=float(score_long[i]),
            score_short=float(score_short[i]),
            signal_strength=str(signal_strength[i]),
            signal_score=float(signal_score[i]),
            rsi=round(float(rsi_arr[i]), 2),
            squeezed=bool(squeezed[i]) if not np.isnan(bb_lo_prev[i]) else False,
            ha_real_divergence_pct=round(float(ha_real_div_pct[i]), 4),
            vol_confirm=bool(vol_spike[i]),
            bars_since_flip=int(bars_active[i]),
            cvd_proxy=round(float(cvd_sum_arr[i]), 4),
            smc_trend=int(smc_trend_arr[i]),
        ))
    return out, atr14, atr22


# ── v4 Phase 1 — Mean-reversion (fade-extremes) signal vectorizer ──────────

# Imported lazily inside the function to avoid a circular import — tracks/
# package depends on signal_features which depends on signal_weights, all of
# which are siblings of mtf_vectorizer in the call graph. Lazy import keeps
# module-load ordering robust.

_MR_BULL_REGIMES = {"BULL_TREND", "BULLISH", "BULL_TRENDING", "BULL_RANGING", "BULL_WEAK"}
_MR_BEAR_REGIMES = {"BEAR_TREND", "BEARISH", "BEAR_TRENDING", "BEAR_RANGING", "BEAR_WEAK"}


def build_mr_signals_full(
    candles_signal: List[Candle],
    regime_labels: np.ndarray,
    *,
    rsi_extreme_high: float = 75.0,
    rsi_extreme_low:  float = 25.0,
    bb_period:        int   = 20,
    bb_std:           float = 2.0,
    vol_climax_window:int   = 100,
    vol_climax_pct:   float = 0.95,
    cvd_window:       int   = 10,
    cvd_min_ratio:    float = 0.3,
    short_bias_boost: float = 2.0,
    # v4 — Edge-stacking gates added when chasing edge_proven on
    # BTC scalping_30m.  Each is opt-in (None / 0 disables).
    entry_hours_utc:  Optional[List[int]] = None,
    wick_rejection_pct: float = 0.0,
    range_z_min:      float = 0.0,
) -> List[SignalResult]:
    """
    Vectorised counterpart to `tracks.fade_extremes.FadeExtremesTrack.compute`.

    For each signal bar emit a SignalResult whose `trend` field encodes the
    TRADE direction (counter-trend) and `signal_score` / `signal_strength`
    encode the fade-extremes confluence. The downstream backtest entry gate
    consumes these exactly like a regular SignalResult — no path-special
    casing required beyond picking which array to read (`vec.signals` vs
    `vec.mr_signals`).

    Knob defaults are FadeExtremesConfig defaults; the search driver
    (`scripts/btc_mr_search.py`) sweeps them.
    """
    df = _candles_to_df(candles_signal)
    n = len(df)
    if n == 0:
        return []

    open_  = df["open"].values
    high   = df["high"].values
    low    = df["low"].values
    close  = df["close"].values
    volume = df["volume"].values

    rsi_arr = compute_rsi(close, 14)

    s_close = pd.Series(close)
    bb_mid = s_close.rolling(bb_period, min_periods=bb_period).mean()
    bb_sd  = s_close.rolling(bb_period, min_periods=bb_period).std(ddof=1)
    bb_hi_arr = (bb_mid + bb_std * bb_sd).values
    bb_lo_arr = (bb_mid - bb_std * bb_sd).values

    # Rolling volume percentile rank (top-X% climax).
    # For each bar i: fraction of last vol_climax_window bars where vol[i] >= vol[j].
    # Implemented as a rolling rank — keeps O(N·log W) which is fast.
    vol_series = pd.Series(volume)
    vol_pct_rank = vol_series.rolling(vol_climax_window, min_periods=10).apply(
        lambda w: float(np.sum(w[-1] >= w)) / len(w),
        raw=True,
    ).values

    # CVD-window — same logic as build_signals_full but exposed for MR.
    tr = high - low
    safe_tr = np.where(tr > 0, tr, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        per_bar_delta = volume * ((close - open_) / safe_tr)
    per_bar_delta = np.nan_to_num(per_bar_delta, nan=0.0)
    per_bar_delta = np.clip(per_bar_delta, -np.abs(volume), np.abs(volume))
    s_delta = pd.Series(per_bar_delta)
    cvd_sum_arr = s_delta.rolling(cvd_window, min_periods=1).sum().values
    abs_sum_arr = s_delta.abs().rolling(cvd_window, min_periods=1).sum().values
    with np.errstate(invalid="ignore", divide="ignore"):
        cvd_ratio = np.where(abs_sum_arr > 0,
                             np.abs(cvd_sum_arr) / abs_sum_arr, 0.0)

    # Trade-direction array: -1 (short = fade rally) in BULL regimes,
    # +1 (long = fade dip) in BEAR regimes, 0 elsewhere (no MR trade).
    entry_dir = np.zeros(n, dtype=np.int64)
    if regime_labels is not None and len(regime_labels) == n:
        for i in range(n):
            lbl = str(regime_labels[i]) if regime_labels[i] else ""
            if lbl in _MR_BULL_REGIMES:
                entry_dir[i] = -1
            elif lbl in _MR_BEAR_REGIMES:
                entry_dir[i] = 1

    # Per-bar feature scores (0..1) given the entry_dir at that bar.
    rsi_extreme_short = rsi_arr > rsi_extreme_high
    rsi_extreme_long  = rsi_arr < rsi_extreme_low
    rsi_extreme_ok = np.where(
        entry_dir == -1, rsi_extreme_short,
        np.where(entry_dir == 1, rsi_extreme_long, False),
    )
    # RSI magnitude score: 0 at threshold, 1 at threshold±10, clipped.
    rsi_mag = np.where(
        entry_dir == -1, np.clip((rsi_arr - rsi_extreme_high) / 10.0, 0.0, 1.0),
        np.where(entry_dir == 1, np.clip((rsi_extreme_low - rsi_arr) / 10.0, 0.0, 1.0), 0.0),
    )
    # BB breach score: 0 if close still inside band, scaled to 1 at half-width past.
    with np.errstate(invalid="ignore"):
        bb_width = np.maximum(bb_hi_arr - bb_lo_arr, 1e-9)
        bb_short = np.where(close > bb_hi_arr, (close - bb_hi_arr) / (bb_width * 0.5), 0.0)
        bb_long  = np.where(close < bb_lo_arr, (bb_lo_arr - close) / (bb_width * 0.5), 0.0)
    bb_score = np.clip(np.where(entry_dir == -1, bb_short,
                                np.where(entry_dir == 1, bb_long, 0.0)),
                       0.0, 1.0)
    # Volume climax (binary).
    vol_score = (vol_pct_rank >= vol_climax_pct).astype(np.float64)
    # CVD confirmation: sign aligns with fade direction AND ratio above floor.
    sign_ok = np.where(
        entry_dir == -1, cvd_sum_arr < 0,
        np.where(entry_dir == 1, cvd_sum_arr > 0, False),
    )
    cvd_score = np.where(sign_ok & (cvd_ratio >= cvd_min_ratio),
                         np.minimum(cvd_ratio, 1.0), 0.0)

    # Score assembly: matches FadeExtremesConfig default weights.
    w_regime, w_rsi, w_bb, w_vol, w_cvd = 6.0, 4.0, 4.0, 3.0, 3.0
    earned = (
        w_regime * 1.0
        + w_rsi * rsi_mag
        + w_bb * bb_score
        + w_vol * vol_score
        + w_cvd * cvd_score
    )
    total = w_regime + w_rsi + w_bb + w_vol + w_cvd   # 20
    pct = earned / total

    # The regime+rsi gates must pass for any trade — else score=0.
    gate_ok = (entry_dir != 0) & rsi_extreme_ok & (bb_score > 0)

    # v4 edge-stacking gate #1: session-hour filter. When supplied, entries
    # only fire during the configured UTC hours (e.g. [13,14,15,16,17] for
    # the US session where BTC bear-side reversion is most reliable).
    if entry_hours_utc:
        ts = np.array([int(c.timestamp_ms) for c in candles_signal], dtype=np.int64)
        bar_hour = ((ts // 3_600_000) % 24).astype(np.int64)
        allowed = np.zeros(n, dtype=bool)
        for h in entry_hours_utc:
            allowed |= (bar_hour == int(h))
        gate_ok = gate_ok & allowed

    # v4 edge-stacking gate #2: rejection-wick requirement. For a SHORT
    # entry (fading a rally) we want an upper wick that's at least
    # `wick_rejection_pct` of the bar range — a sellers-show-up candle.
    # For a LONG entry (fading a dip), the lower wick rejection requirement.
    if wick_rejection_pct > 0.0:
        bar_range = high - low
        body_top  = np.maximum(open_, close)
        body_bot  = np.minimum(open_, close)
        with np.errstate(invalid="ignore", divide="ignore"):
            upper_wick_frac = np.where(bar_range > 0, (high - body_top) / bar_range, 0.0)
            lower_wick_frac = np.where(bar_range > 0, (body_bot - low) / bar_range, 0.0)
        wick_ok = np.where(
            entry_dir == -1, upper_wick_frac >= wick_rejection_pct,
            np.where(entry_dir == 1, lower_wick_frac >= wick_rejection_pct, False),
        )
        gate_ok = gate_ok & wick_ok

    # v4 edge-stacking gate #3: minimum range z-score. Filters bars whose
    # range is too compressed to be a real climax — flat-range "rallies"
    # are usually drift, not the kind of move that reverses.
    if range_z_min > 0.0:
        bar_range_full = high - low
        s_r = pd.Series(bar_range_full)
        r_mean = s_r.rolling(50, min_periods=10).mean()
        r_std  = s_r.rolling(50, min_periods=10).std(ddof=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            range_z = (bar_range_full - r_mean) / r_std.where(r_std > 1e-12, np.nan)
        range_z = np.nan_to_num(range_z.values, nan=0.0)
        gate_ok = gate_ok & (range_z >= range_z_min)

    pct = np.where(gate_ok, pct, 0.0)
    score = np.round(pct * 20.0, 2)
    # Short-side boost (BTC asymmetry).
    score = np.where(entry_dir == -1, np.minimum(20.0, score + short_bias_boost), score)

    strength = np.where(pct >= 0.75, "STRONG",
                        np.where(pct >= 0.35, "SIGNAL", "NONE"))

    out: List[SignalResult] = []
    for i in range(n):
        if i < 30 or not gate_ok[i]:
            out.append(SignalResult(
                trend=0, all_green=False, all_red=False,
                green_arrow=False, red_arrow=False,
                st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
                close_1h=float(close[i]),
                score_long=0.0, score_short=0.0,
            ))
            continue
        d = int(entry_dir[i])
        out.append(SignalResult(
            trend=d,
            all_green=False, all_red=False,
            green_arrow=False, red_arrow=False,
            st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
            close_1h=float(close[i]),
            score_long=float(score[i]) if d == 1 else 0.0,
            score_short=float(score[i]) if d == -1 else 0.0,
            signal_strength=str(strength[i]),
            signal_score=float(score[i]),
            rsi=round(float(rsi_arr[i]), 2),
            squeezed=False,
            vol_confirm=bool(vol_score[i]),
            bars_since_flip=0,
            cvd_proxy=round(float(cvd_sum_arr[i]), 4),
            ha_real_divergence_pct=0.0,
        ))
    return out


# ── Top-level API ─────────────────────────────────────────────────────────────


def vectorize_replay(
    candles_signal: List[Candle],
    candles_regime: List[Candle],
    *,
    signal_bar_ms: int,
    regime_bar_ms: int,
    st_configs: Optional[List[Tuple[int, float]]] = None,
    idle_strictness: str = "auto",
    build_mr: bool = False,
    mr_config: Optional[Dict[str, Any]] = None,
) -> VectorizedReplay:
    """
    Pre-compute everything the MTF replay loop needs in O(N) time.

    Returns aligned lists where:
      * `signals[i]`  is the SignalResult at signal bar i.
      * `regimes_per_regime_bar[k]` is the RegimeResult at regime bar k.
      * `regime_idx_at_signal[i]` is the count of regime bars whose CLOSE
        timestamp has elapsed by signal bar i (matches the legacy cursor).
        The replay loop indexes regimes with `regime_idx_at_signal[i] - 1`.

    Pure: no I/O. Idle-strictness defaults to "auto" which reads the same
    env var the live regime engine reads at module load.
    """
    regimes, regime_atr14 = build_regimes_full(
        candles_regime, idle_strictness=idle_strictness,
    )

    signal_ts = np.array(
        [c.timestamp_ms for c in candles_signal], dtype=np.int64,
    )
    regime_ts = np.array(
        [c.timestamp_ms for c in candles_regime], dtype=np.int64,
    )
    regime_idx_at_signal = map_regime_idx_to_signal(
        signal_ts, regime_ts, regime_bar_ms,
    )

    # v4 — Build per-signal-bar regime label array so build_signals_full can
    # apply regime-aware weights. A label of "" indicates "no regime yet"
    # (warmup bars) which falls back to base weights.
    regime_labels_per_signal_bar: List[str] = []
    for idx_at_sig in regime_idx_at_signal:
        if idx_at_sig < 1 or idx_at_sig > len(regimes):
            regime_labels_per_signal_bar.append("")
        else:
            regime_labels_per_signal_bar.append(regimes[int(idx_at_sig) - 1].macro_regime.value)
    regime_labels_arr = np.asarray(regime_labels_per_signal_bar, dtype=object)

    signals, signal_atr14, signal_atr22 = build_signals_full(
        candles_signal, st_configs=st_configs,
        regime_labels=regime_labels_arr,
    )

    # v4 Phase 1 — Mean-reversion signals (fade-extremes). Only computed when
    # the caller asks for them via `build_mr=True`; the cost is roughly an
    # extra 0.5x of the trend-following compute (rolling RSI/BB/volume rank +
    # CVD reused from build_signals_full's internals — we recompute here so
    # the MR vectorizer stays self-contained). Defaults to None to keep
    # existing callers byte-identical.
    mr_signals: Optional[List[SignalResult]] = None
    if build_mr:
        mr_kwargs = dict(mr_config or {})
        mr_signals = build_mr_signals_full(
            candles_signal, regime_labels_arr, **mr_kwargs,
        )

    return VectorizedReplay(
        n_signal=len(signals),
        n_regime=len(regimes),
        regimes_per_regime_bar=regimes,
        signals=signals,
        regime_idx_at_signal=regime_idx_at_signal,
        signal_atr14=signal_atr14,
        signal_atr22=signal_atr22,
        regime_atr14=regime_atr14,
        mr_signals=mr_signals,
    )
