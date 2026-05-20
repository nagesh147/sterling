"""
Sterling v4 Phase 2 — Microstructure feature library + scoring layer.

The Sterling reference DB ships OHLCV only (no funding-rate history, no
perp-basis history, no L2 book). At sub-1H bars OHLCV alone misses
information that drives forward returns — but it does ENCODE several
useful microstructure-like signals which we can extract:

  • Liquidation-cascade proxy: bar with extreme range + reverse close
    (long wick into a stop hunt followed by reversal)
  • Volume profile imbalance: this bar's volume concentration vs the
    rolling 100-bar mean — flags institutional sweeps
  • CVD acceleration: change in 10-bar CVD over the most-recent 5 bars
    — flags tape-flip events
  • Range expansion z-score: (bar_range − mean) / std of last 50 bars
    — flags break-of-structure
  • Body-to-range ratio: |close - open| / (high - low)
    — climax-vs-rejection candle shape

These are not as good as real funding-rate / book / OI features, but they
materially supplement the fade-extremes track by adding tape-quality
context. When a real microstructure data ingestion lands, replace
these proxies with the actual features (same function signature).

The track exposes one score [0..1] per bar that the mean_reversion track
blends into its final score. It does not emit independent trades.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class MicrostructureConfig:
    """Tunable knobs for the microstructure proxy scoring."""
    range_z_window:        int   = 50    # window for range expansion z-score
    range_z_threshold:     float = 1.5   # bar range > μ + 1.5σ → expansion
    vol_z_window:          int   = 100   # window for volume z-score
    vol_z_threshold:       float = 1.5
    cvd_window:            int   = 10
    cvd_accel_window:      int   = 5
    cvd_accel_threshold:   float = 0.5   # |ΔCVD_5| / Σ|delta_10| > this
    liquidation_range_x:   float = 3.0   # bar range > 3×ATR(14) is candidate
    liquidation_wick_pct:  float = 0.5   # >50% of range is wick → rejection
    score_w_range_z:       float = 1.0
    score_w_vol_z:         float = 1.0
    score_w_cvd_accel:     float = 1.5
    score_w_liquidation:   float = 2.0
    score_w_body_quality:  float = 0.5


@dataclass(frozen=True)
class MicrostructureScores:
    """Per-bar microstructure proxy scores (each in [0, 1]).

    `combined` is the weighted sum normalised to [0, 1]. Use it directly as
    a multiplicative or additive blend term in the mean_reversion track.
    `features` carries the raw components for debug / postmortem.
    """
    combined: np.ndarray                 # shape (N,) ∈ [0, 1]
    features: Dict[str, np.ndarray]      # named arrays for debug


def compute_microstructure_scores(
    open_:  np.ndarray,
    high:   np.ndarray,
    low:    np.ndarray,
    close:  np.ndarray,
    volume: np.ndarray,
    atr14:  np.ndarray,
    direction: int,                       # +1 long entry, -1 short entry
    *,
    config: Optional[MicrostructureConfig] = None,
) -> MicrostructureScores:
    """Vectorised microstructure proxy scoring.

    For a SHORT entry (`direction=-1` — fading a rally), the favourable
    pattern is: range expansion + volume surge + CVD turning negative +
    liquidation-style rejection candle with upper wick. For a LONG entry
    (`direction=1`), the mirror image — lower wick rejection. Bars that
    don't fit the direction return 0 for the directional components.

    All outputs in [0, 1]. NaN-safe via np.nan_to_num at each stage.
    """
    cfg = config or MicrostructureConfig()
    n = close.shape[0]
    if n == 0:
        return MicrostructureScores(np.zeros(0), {})

    import pandas as pd

    # ── Range expansion z-score ─────────────────────────────────────────
    bar_range = high - low
    s_range = pd.Series(bar_range)
    range_mean = s_range.rolling(cfg.range_z_window, min_periods=10).mean()
    range_std  = s_range.rolling(cfg.range_z_window, min_periods=10).std(ddof=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        range_z = (bar_range - range_mean) / range_std.where(range_std > 1e-12, np.nan)
    range_z_arr = np.nan_to_num(range_z.values, nan=0.0)
    # Score: clipped (z - threshold) / 2 → 0 below threshold, 1 at z=threshold+2
    range_score = np.clip((range_z_arr - cfg.range_z_threshold) / 2.0, 0.0, 1.0)

    # ── Volume z-score ──────────────────────────────────────────────────
    s_vol = pd.Series(volume)
    vol_mean = s_vol.rolling(cfg.vol_z_window, min_periods=10).mean()
    vol_std  = s_vol.rolling(cfg.vol_z_window, min_periods=10).std(ddof=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        vol_z = (volume - vol_mean) / vol_std.where(vol_std > 1e-12, np.nan)
    vol_z_arr = np.nan_to_num(vol_z.values, nan=0.0)
    vol_score = np.clip((vol_z_arr - cfg.vol_z_threshold) / 2.0, 0.0, 1.0)

    # ── CVD acceleration ─────────────────────────────────────────────────
    tr = bar_range
    safe_tr = np.where(tr > 0, tr, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        per_bar_delta = volume * ((close - open_) / safe_tr)
    per_bar_delta = np.nan_to_num(per_bar_delta, nan=0.0)
    per_bar_delta = np.clip(per_bar_delta, -np.abs(volume), np.abs(volume))
    s_delta = pd.Series(per_bar_delta)
    cvd_10 = s_delta.rolling(cfg.cvd_window, min_periods=1).sum().values
    cvd_5  = s_delta.rolling(cfg.cvd_accel_window, min_periods=1).sum().values
    abs_10 = s_delta.abs().rolling(cfg.cvd_window, min_periods=1).sum().values
    with np.errstate(invalid="ignore", divide="ignore"):
        accel = np.where(abs_10 > 0, cvd_5 / abs_10, 0.0)
    # Direction-aware: for SHORT entry, want CVD acceleration NEGATIVE
    # (selling pressure absorbing). For LONG entry, want POSITIVE.
    if direction == -1:
        dir_score = np.where(accel < -cfg.cvd_accel_threshold,
                             np.minimum(1.0, abs(accel)), 0.0)
    elif direction == 1:
        dir_score = np.where(accel > cfg.cvd_accel_threshold,
                             np.minimum(1.0, abs(accel)), 0.0)
    else:
        dir_score = np.zeros(n, dtype=np.float64)
    cvd_score = dir_score

    # ── Liquidation cascade proxy ────────────────────────────────────────
    # Bar where range > 3×ATR AND wick on the entry side > 50% of range.
    # For SHORT entry (fading a top): upper-wick rejection.
    # For LONG  entry (fading a bottom): lower-wick rejection.
    with np.errstate(invalid="ignore"):
        big_bar = (atr14 > 0) & (bar_range > cfg.liquidation_range_x * atr14)
    body_top = np.maximum(open_, close)
    body_bot = np.minimum(open_, close)
    upper_wick = high - body_top
    lower_wick = body_bot - low
    with np.errstate(invalid="ignore", divide="ignore"):
        upper_wick_frac = np.where(bar_range > 0, upper_wick / bar_range, 0.0)
        lower_wick_frac = np.where(bar_range > 0, lower_wick / bar_range, 0.0)
    if direction == -1:
        liquidation_ok = big_bar & (upper_wick_frac > cfg.liquidation_wick_pct)
    elif direction == 1:
        liquidation_ok = big_bar & (lower_wick_frac > cfg.liquidation_wick_pct)
    else:
        liquidation_ok = np.zeros(n, dtype=bool)
    liquidation_score = liquidation_ok.astype(np.float64)

    # ── Body-to-range quality ───────────────────────────────────────────
    # Indecisive bar (small body) is fine for fade entry; long body in entry
    # direction is bad (price still extending). For SHORT entry want bar
    # body NOT bullish-dominant; for LONG want body NOT bearish-dominant.
    with np.errstate(invalid="ignore", divide="ignore"):
        body_frac = np.where(bar_range > 0,
                             np.abs(close - open_) / bar_range, 0.0)
    is_bullish_body = close > open_
    if direction == -1:
        # Long upper wick + bearish/small body = good
        body_quality = np.where(
            ~is_bullish_body | (body_frac < 0.4), 1.0, 0.0,
        )
    elif direction == 1:
        body_quality = np.where(
            is_bullish_body | (body_frac < 0.4), 1.0, 0.0,
        )
    else:
        body_quality = np.zeros(n, dtype=np.float64)

    # ── Weighted combine ─────────────────────────────────────────────────
    w_total = (cfg.score_w_range_z + cfg.score_w_vol_z + cfg.score_w_cvd_accel
               + cfg.score_w_liquidation + cfg.score_w_body_quality)
    combined = (
        cfg.score_w_range_z       * range_score
        + cfg.score_w_vol_z       * vol_score
        + cfg.score_w_cvd_accel   * cvd_score
        + cfg.score_w_liquidation * liquidation_score
        + cfg.score_w_body_quality* body_quality
    ) / max(w_total, 1e-9)
    combined = np.clip(combined, 0.0, 1.0)

    return MicrostructureScores(
        combined=combined,
        features={
            "range_z":     range_z_arr,
            "vol_z":       vol_z_arr,
            "cvd_accel":   accel,
            "liq_ok":      liquidation_ok.astype(np.float64),
            "body_quality":body_quality,
            "range_score": range_score,
            "vol_score":   vol_score,
            "cvd_score":   cvd_score,
            "liq_score":   liquidation_score,
        },
    )


# ── Per-bar live API (mirrors signal_features pattern) ────────────────────

def microstructure_score_at(
    open_arr:  np.ndarray,
    high_arr:  np.ndarray,
    low_arr:   np.ndarray,
    close_arr: np.ndarray,
    volume_arr:np.ndarray,
    atr14_arr: np.ndarray,
    direction: int,
    *,
    config: Optional[MicrostructureConfig] = None,
) -> Tuple[float, Dict[str, float]]:
    """Live (latest-bar) microstructure score. Wraps the vectorised compute
    and returns the last bar's value plus a dict of raw components."""
    scores = compute_microstructure_scores(
        open_arr, high_arr, low_arr, close_arr, volume_arr, atr14_arr,
        direction, config=config,
    )
    if scores.combined.size == 0:
        return 0.0, {}
    last = float(scores.combined[-1])
    feats = {k: float(v[-1]) for k, v in scores.features.items()}
    return last, feats
