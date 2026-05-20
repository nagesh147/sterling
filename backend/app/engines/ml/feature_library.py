"""
Sterling v4 Phase 3 — ML feature library.

Bar-level feature extraction used by the xgboost ensemble track. Each
feature is computable from OHLCV alone so the library works against the
existing `sterling_paper.db` schema. Replace OHLCV-derived microstructure
proxies with real funding/OI/L2 features when that data ingestion lands —
the function signature stays stable.

The library exposes one entry point:

    build_feature_matrix(candles_signal, candles_regime, ...) -> (X, ts, ...)

which returns a 2-D numpy array (N × n_features) aligned to `candles_signal`.
The matrix layout is column-stable across runs via `FEATURE_NAMES`.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.schemas.market import Candle
from app.engines.indicators.atr import compute_atr
from app.engines.indicators.adx import adx as compute_adx
from app.engines.indicators.bollinger import bollinger_bands
from app.engines.indicators.ema import compute_ema
from app.engines.indicators.heikin_ashi import compute_heikin_ashi, ha_body_bull
from app.engines.indicators.rsi import rsi as compute_rsi
from app.engines.indicators.supertrend import compute_supertrend
from app.engines.directional.tracks.microstructure import (
    compute_microstructure_scores, MicrostructureConfig,
)


# Stable column order — DO NOT reorder; the trained model encodes this layout.
FEATURE_NAMES: List[str] = [
    "rsi_14",
    "rsi_14_change_5",
    "atr_pct",                   # ATR / close
    "atr_pct_z_50",
    "adx_14",
    "bb_width_pct",              # (bb_hi - bb_lo) / close
    "bb_position",               # (close - bb_lo) / (bb_hi - bb_lo)
    "ema_distance_pct_20",
    "ema_distance_pct_55",
    "ema_21_55_cross",           # sign(ema21 - ema55)
    "supertrend_count",          # number of agreeing STs at this bar
    "ha_bull",                   # HA candle bullish? 1/0
    "ha_real_div_pct",
    "vol_z_50",
    "vol_climax_pct_rank_100",
    "range_z_50",
    "body_to_range",
    "upper_wick_frac",
    "lower_wick_frac",
    "cvd_10",                    # 10-bar CVD-proxy sum (raw)
    "cvd_ratio",                 # |cvd_10| / sum(|delta_10|)
    "cvd_5_minus_10",            # acceleration: cvd_5 - cvd_10
    "ret_1",                     # 1-bar log return
    "ret_5",
    "ret_20",
    "ret_5_std",                 # 5-bar realised vol
    "ret_20_std",
    "micro_combined_short",      # microstructure score assuming SHORT entry
    "micro_combined_long",       # microstructure score assuming LONG entry
    "hour_utc",                  # bar hour 0..23 (categorical → numeric)
    "weekday",                   # bar weekday 0..6
    "regime_bull",               # 1 if HTF regime is bullish
    "regime_bear",               # 1 if HTF regime is bearish
    "regime_volatile",           # 1 if HTF regime is volatile
    "regime_idle",               # 1 if HTF regime is idle
    "regime_atr_pct",            # HTF ATR percentile (broadcast)
    "regime_adx",                # HTF ADX (broadcast)
]


def _broadcast_regime(
    regime_close_ts_ms: np.ndarray,
    regime_values:      np.ndarray,
    signal_ts_ms:       np.ndarray,
    regime_bar_ms:      int,
) -> np.ndarray:
    """Broadcast a per-regime-bar series to the signal-bar axis."""
    out = np.zeros_like(signal_ts_ms, dtype=np.float64)
    if regime_values.size == 0:
        return out
    reg_close = regime_close_ts_ms + regime_bar_ms
    idx = np.searchsorted(reg_close, signal_ts_ms, side="right")
    idx = np.clip(idx - 1, 0, regime_values.size - 1)
    out[:] = regime_values[idx]
    return out


def build_feature_matrix(
    candles_signal: List[Candle],
    candles_regime: List[Candle],
    *,
    regime_bar_ms: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute the full feature matrix.

    Returns:
      X — shape (N_signal, len(FEATURE_NAMES)) float64.
      ts — shape (N_signal,) timestamp_ms per row, for downstream joining.

    Bars where any feature is NaN (warmup) get the row filled with 0.0 and
    the caller is responsible for masking via `(X.sum(axis=1) != 0)` or by
    skipping the first ~50 rows.
    """
    n = len(candles_signal)
    if n == 0:
        return np.zeros((0, len(FEATURE_NAMES))), np.zeros(0, dtype=np.int64)

    o = np.array([c.open  for c in candles_signal], dtype=np.float64)
    h = np.array([c.high  for c in candles_signal], dtype=np.float64)
    l = np.array([c.low   for c in candles_signal], dtype=np.float64)
    c = np.array([c.close for c in candles_signal], dtype=np.float64)
    v = np.array([c.volume for c in candles_signal], dtype=np.float64)
    ts = np.array([c.timestamp_ms for c in candles_signal], dtype=np.int64)

    # Indicators.
    rsi_14 = compute_rsi(c, 14)
    rsi_14_chg_5 = pd.Series(rsi_14).diff(5).fillna(0).values
    atr_14 = compute_atr(h, l, c, 14)
    atr_pct = np.where(c > 0, atr_14 / c, 0.0)
    atr_pct_mean = pd.Series(atr_pct).rolling(50, min_periods=10).mean()
    atr_pct_std  = pd.Series(atr_pct).rolling(50, min_periods=10).std(ddof=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        atr_pct_z = (atr_pct - atr_pct_mean) / atr_pct_std.where(atr_pct_std > 1e-12, np.nan)
    atr_pct_z = np.nan_to_num(atr_pct_z.values, nan=0.0)
    adx_14 = compute_adx(h, l, c, 14)
    bb_lo, bb_mid, bb_hi = bollinger_bands(c, 20, 2.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        bb_width = np.where(c > 0, (bb_hi - bb_lo) / c, 0.0)
        bb_pos = np.where((bb_hi - bb_lo) > 0,
                          (c - bb_lo) / (bb_hi - bb_lo), 0.5)
    ema20 = compute_ema(c, 20)
    ema55 = compute_ema(c, 55)
    with np.errstate(invalid="ignore", divide="ignore"):
        ema20_dist = np.where(c > 0, (c - ema20) / c, 0.0)
        ema55_dist = np.where(c > 0, (c - ema55) / c, 0.0)
    ema21 = compute_ema(c, 21)
    ema_cross = np.sign(ema21 - ema55)
    st1_line, st1_t = compute_supertrend(h, l, c, 7, 3.0)
    st2_line, st2_t = compute_supertrend(h, l, c, 14, 2.0)
    st3_line, st3_t = compute_supertrend(h, l, c, 21, 2.0)
    st_count = (st1_t == 1).astype(int) + (st2_t == 1).astype(int) + (st3_t == 1).astype(int)
    st_count = st_count - ((st1_t == -1).astype(int) + (st2_t == -1).astype(int) + (st3_t == -1).astype(int))
    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)
    ha_bull = ha_body_bull(o, h, l, c).astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        ha_real_div = np.where(c > 0, np.abs(c - ha_c) / c * 100.0, 0.0)

    # Volume features.
    s_v = pd.Series(v)
    vol_mean = s_v.rolling(50, min_periods=10).mean()
    vol_std  = s_v.rolling(50, min_periods=10).std(ddof=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        vol_z = (v - vol_mean) / vol_std.where(vol_std > 1e-12, np.nan)
    vol_z = np.nan_to_num(vol_z.values, nan=0.0)
    vol_pct_rank = s_v.rolling(100, min_periods=10).apply(
        lambda w: float(np.sum(w[-1] >= w)) / len(w), raw=True,
    ).fillna(0).values

    # Range / wick features.
    bar_range = h - l
    s_r = pd.Series(bar_range)
    range_mean = s_r.rolling(50, min_periods=10).mean()
    range_std  = s_r.rolling(50, min_periods=10).std(ddof=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        range_z = (bar_range - range_mean) / range_std.where(range_std > 1e-12, np.nan)
    range_z = np.nan_to_num(range_z.values, nan=0.0)
    body_top = np.maximum(o, c)
    body_bot = np.minimum(o, c)
    with np.errstate(invalid="ignore", divide="ignore"):
        body_to_range = np.where(bar_range > 0, np.abs(c - o) / bar_range, 0.0)
        upper_wick_frac = np.where(bar_range > 0, (h - body_top) / bar_range, 0.0)
        lower_wick_frac = np.where(bar_range > 0, (body_bot - l) / bar_range, 0.0)

    # CVD features (10-bar + 5-bar).
    safe_tr = np.where(bar_range > 0, bar_range, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        per_bar_delta = v * ((c - o) / safe_tr)
    per_bar_delta = np.nan_to_num(per_bar_delta, nan=0.0)
    per_bar_delta = np.clip(per_bar_delta, -np.abs(v), np.abs(v))
    s_delta = pd.Series(per_bar_delta)
    cvd_10 = s_delta.rolling(10, min_periods=1).sum().values
    cvd_5  = s_delta.rolling(5,  min_periods=1).sum().values
    abs_10 = s_delta.abs().rolling(10, min_periods=1).sum().values
    with np.errstate(invalid="ignore", divide="ignore"):
        cvd_ratio = np.where(abs_10 > 0, np.abs(cvd_10) / abs_10, 0.0)
    cvd_5_minus_10 = cvd_5 - cvd_10

    # Returns + realised vol.
    with np.errstate(invalid="ignore", divide="ignore"):
        ret_series = np.diff(np.log(np.where(c > 0, c, np.nan)))
    ret_series = np.concatenate(([0.0], np.nan_to_num(ret_series, nan=0.0)))
    s_ret = pd.Series(ret_series)
    ret_5  = s_ret.rolling(5,  min_periods=1).sum().values
    ret_20 = s_ret.rolling(20, min_periods=1).sum().values
    ret_5_std  = s_ret.rolling(5,  min_periods=2).std(ddof=0).fillna(0).values
    ret_20_std = s_ret.rolling(20, min_periods=2).std(ddof=0).fillna(0).values

    # Microstructure (both directions — model decides which).
    micro_short = compute_microstructure_scores(o, h, l, c, v, atr_14, -1).combined
    micro_long  = compute_microstructure_scores(o, h, l, c, v, atr_14,  1).combined

    # Time-of-day / day-of-week.
    hours    = ((ts // 3_600_000) % 24).astype(np.float64)
    weekdays = (((ts // 86_400_000) + 4) % 7).astype(np.float64)  # Jan 1 1970 was Thursday=4

    # HTF regime broadcast.
    n_reg = len(candles_regime)
    if n_reg > 0:
        r_h = np.array([cd.high for cd in candles_regime], dtype=np.float64)
        r_l = np.array([cd.low  for cd in candles_regime], dtype=np.float64)
        r_c = np.array([cd.close for cd in candles_regime], dtype=np.float64)
        r_ts = np.array([cd.timestamp_ms for cd in candles_regime], dtype=np.int64)
        r_atr  = compute_atr(r_h, r_l, r_c, 14)
        r_atr_pct_mean = pd.Series(r_atr).rolling(100, min_periods=10).mean().fillna(0).values
        with np.errstate(invalid="ignore", divide="ignore"):
            r_atr_pct = np.where(r_c > 0, r_atr / r_c, 0.0)
        # Simple percentile rank of latest vs rolling 100-bar window.
        r_atr_pct_rank = pd.Series(r_atr_pct).rolling(100, min_periods=10).apply(
            lambda w: float(np.sum(w[-1] >= w)) / len(w) * 100.0, raw=True,
        ).fillna(50.0).values
        r_adx = compute_adx(r_h, r_l, r_c, 14)
        r_ema21 = compute_ema(r_c, 21)
        r_ema55 = compute_ema(r_c, 55)
        # Regime labels (simplified): bull if ema21>ema55 and close>ema21 and adx>=15
        regime_bull = ((r_ema21 > r_ema55) & (r_c > r_ema21) & (r_adx >= 15.0)).astype(np.float64)
        regime_bear = ((r_ema21 < r_ema55) & (r_c < r_ema21) & (r_adx >= 15.0)).astype(np.float64)
        regime_volatile = ((r_atr_pct_rank > 65.0) & (r_adx < 20.0)).astype(np.float64)
        regime_idle = ((r_atr_pct_rank < 30.0) & (r_adx < 15.0)).astype(np.float64)
        f_bull = _broadcast_regime(r_ts, regime_bull, ts, regime_bar_ms)
        f_bear = _broadcast_regime(r_ts, regime_bear, ts, regime_bar_ms)
        f_vol  = _broadcast_regime(r_ts, regime_volatile, ts, regime_bar_ms)
        f_idle = _broadcast_regime(r_ts, regime_idle, ts, regime_bar_ms)
        f_atr_pct = _broadcast_regime(r_ts, r_atr_pct_rank, ts, regime_bar_ms)
        f_adx     = _broadcast_regime(r_ts, r_adx, ts, regime_bar_ms)
    else:
        f_bull = f_bear = f_vol = f_idle = np.zeros(n)
        f_atr_pct = np.full(n, 50.0)
        f_adx = np.zeros(n)

    # Stack into matrix (column order MUST match FEATURE_NAMES).
    cols = [
        rsi_14, rsi_14_chg_5, atr_pct, atr_pct_z, adx_14, bb_width, bb_pos,
        ema20_dist, ema55_dist, ema_cross,
        st_count.astype(np.float64), ha_bull, ha_real_div,
        vol_z, vol_pct_rank,
        range_z, body_to_range, upper_wick_frac, lower_wick_frac,
        cvd_10, cvd_ratio, cvd_5_minus_10,
        ret_series, ret_5, ret_20, ret_5_std, ret_20_std,
        micro_short, micro_long,
        hours, weekdays,
        f_bull, f_bear, f_vol, f_idle, f_atr_pct, f_adx,
    ]
    # Sanity — column count matches the names.
    assert len(cols) == len(FEATURE_NAMES), (
        f"Feature column count mismatch: {len(cols)} cols vs "
        f"{len(FEATURE_NAMES)} names"
    )
    X = np.vstack([np.nan_to_num(np.asarray(col, dtype=np.float64), nan=0.0)
                   for col in cols]).T
    return X, ts
