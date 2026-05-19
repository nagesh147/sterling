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
from dataclasses import dataclass
from typing import List, Optional, Tuple

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

# Tier C #14 — CVD proxy constants (mirror signal_engine).
_CVD_WINDOW = 10
_CVD_DIVERGENCE_PENALTY = 3.0
# Heavily-divergent threshold: |CVD_10| / sum(|delta_10|) > 0.5 AND opposite sign to trend.
_CVD_DIVERGENCE_RATIO = 0.5

# Mirrors signal_engine.compute_signal scoring weights / strength bands.
_SIG_WEIGHTS = {
    "st_flip":         3,
    "rsi":             2,
    "rsi_momentum":    1,
    "squeeze":         4,
    "volume":          4,
    "ha_aligned":      4,
    "ha_real_aligned": 2,
}
_SIG_TOTAL_WEIGHT = sum(_SIG_WEIGHTS.values())  # 20

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
) -> Tuple[List[SignalResult], np.ndarray, np.ndarray]:
    """
    Vectorised signal computation — one SignalResult per signal bar plus the
    ATR(14) and ATR(22) arrays used by the replay loop's stop / trail logic.

    Mirrors `signal_engine.compute_signal` but every indicator runs once over
    the full series via Pandas .rolling() / .ewm() / .shift() and the existing
    numpy helpers. The early warmup window (≲ 30 bars) returns a degenerate
    SignalResult to match the legacy short-circuit.
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
    bb_mid = s_close.rolling(20, min_periods=20).mean()
    bb_std = s_close.rolling(20, min_periods=20).std(ddof=1)
    bb_hi_arr = (bb_mid + 2.0 * bb_std).values
    bb_lo_arr = (bb_mid - 2.0 * bb_std).values

    # Keltner Channels via EMA20 ± 1.5 · ATR10.
    kc_mid = compute_ema(close, 20)
    kc_atr = compute_atr(high, low, close, 10)
    kc_hi_arr = kc_mid + 1.5 * kc_atr
    kc_lo_arr = kc_mid - 1.5 * kc_atr

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

    # Volume spike: vol > 1.5 × rolling-median volume.
    with np.errstate(invalid="ignore", divide="ignore"):
        vol_spike = (vol_median > 0) & (volume > 1.5 * vol_median)

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
    ha_real_aligned = ha_real_div_pct < 0.3

    # RSI gates / momentum bonus.
    rsi_ok_long = (rsi_arr > 42.0) & (rsi_arr < 70.0)
    rsi_ok_short = (rsi_arr > 30.0) & (rsi_arr < 57.0)
    rsi_ok = np.where(
        trend == 1, rsi_ok_long,
        np.where(trend == -1, rsi_ok_short, False),
    ).astype(bool)
    rsi_momentum_long = (rsi_arr > 55.0) & (rsi_arr < 68.0)
    rsi_momentum_short = (rsi_arr > 32.0) & (rsi_arr < 45.0)
    rsi_momentum = np.where(
        trend == 1, rsi_momentum_long,
        np.where(trend == -1, rsi_momentum_short, False),
    ).astype(bool)

    # Earned weight per bar.
    earned = (
        st_flip * _SIG_WEIGHTS["st_flip"]
        + rsi_ok * _SIG_WEIGHTS["rsi"]
        + rsi_momentum * _SIG_WEIGHTS["rsi_momentum"]
        + squeeze_ok * _SIG_WEIGHTS["squeeze"]
        + vol_spike * _SIG_WEIGHTS["volume"]
        + ha_aligned * _SIG_WEIGHTS["ha_aligned"]
        + ha_real_aligned * _SIG_WEIGHTS["ha_real_aligned"]
    ).astype(np.float64)

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
    pct = earned_adj / _SIG_TOTAL_WEIGHT
    signal_score = np.round(pct * 20.0, 2)

    signal_strength = np.where(
        pct >= 0.75, "STRONG",
        np.where(pct >= 0.35, "SIGNAL", "NONE"),
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


# ── Top-level API ─────────────────────────────────────────────────────────────


def vectorize_replay(
    candles_signal: List[Candle],
    candles_regime: List[Candle],
    *,
    signal_bar_ms: int,
    regime_bar_ms: int,
    st_configs: Optional[List[Tuple[int, float]]] = None,
    idle_strictness: str = "auto",
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
    signals, signal_atr14, signal_atr22 = build_signals_full(
        candles_signal, st_configs=st_configs,
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

    return VectorizedReplay(
        n_signal=len(signals),
        n_regime=len(regimes),
        regimes_per_regime_bar=regimes,
        signals=signals,
        regime_idx_at_signal=regime_idx_at_signal,
        signal_atr14=signal_atr14,
        signal_atr22=signal_atr22,
        regime_atr14=regime_atr14,
    )
