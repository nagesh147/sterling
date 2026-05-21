"""
Sterling v4 — Signal Engine.

Per-bar live signal computation. Thin orchestration over
`signal_features` building blocks; weights and thresholds live in
`signal_weights`. This file owns:

  * Candle → numpy array conversion (with the VWAP-adjusted ST3 series).
  * Heikin-Ashi + Supertrend ×3 invocation.
  * SignalResult assembly and caching.

It does NOT own:

  * Confluence weights — `signal_weights.V4_BASE_WEIGHTS`.
  * RSI/volume/squeeze thresholds — `signal_weights.SignalThresholds`.
  * Per-flag feature evaluation — `signal_features.*_state_at`.

The vectorised backtest path (`mtf_vectorizer.build_signals_full`)
shares the same weights + thresholds, so backtest and live agree on
what a given signal_score means.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Generator, List, Optional, Tuple

import numpy as np

from app.schemas.market import Candle
from app.schemas.directional import SignalResult
from app.engines.indicators.heikin_ashi import compute_heikin_ashi, ha_body_bull
from app.engines.indicators.supertrend import compute_supertrend
from app.engines.indicators.rsi import rsi as compute_rsi
from app.engines.indicators.bollinger import bollinger_bands
from app.engines.indicators.keltner import keltner

from app.engines.directional.signal_weights import (
    SignalThresholds, DEFAULT_THRESHOLDS,
)
from app.engines.directional.signal_features import (
    flip_state_at, rsi_state_at, squeeze_state_at,
    ha_state_at, volume_state_at, cvd_state_at,
    staleness_lookback_at, mtf_boost_at, assemble_signal_score,
)
from app.engines.indicators.atr import compute_atr


# ── Back-compat shims (kept for existing tests / call sites) ─────────────

def _rsi_ok_long(rsi: float) -> bool:
    """Long-entry RSI gate. Bounds come from `signal_weights.V4_RSI_LONG_LO/HI`."""
    return DEFAULT_THRESHOLDS.rsi_long_lo < float(rsi) < DEFAULT_THRESHOLDS.rsi_long_hi


def _rsi_ok_short(rsi: float) -> bool:
    """Short-entry RSI gate. Bounds come from `signal_weights.V4_RSI_SHORT_LO/HI`."""
    return DEFAULT_THRESHOLDS.rsi_short_lo < float(rsi) < DEFAULT_THRESHOLDS.rsi_short_hi


# ── VWAP candle generator — exposed for the chart endpoint ────────────────

def _to_vwap_candles(candles: List[Candle]) -> Generator[Candle, None, None]:
    """
    Replace close with cumulative VWAP per session (reset at 00:00 UTC).
    H/L/Open are shifted by the same VWAP offset so ATR stays proportional
    and the supertrend is not distorted by VWAP lag relative to real price.

    Kept as a generator for the chart endpoint that streams VWAP candles
    one at a time. The hot signal path uses the array form below.
    """
    sessions: dict = {}
    for c in candles:
        day_key = c.timestamp_ms // 86_400_000
        if day_key not in sessions:
            sessions[day_key] = {"cum_pv": 0.0, "cum_vol": 0.0}
        typical = (c.high + c.low + c.close) / 3.0
        sessions[day_key]["cum_pv"] += typical * c.volume
        sessions[day_key]["cum_vol"] += c.volume
        vwap = (
            sessions[day_key]["cum_pv"] / sessions[day_key]["cum_vol"]
            if sessions[day_key]["cum_vol"] > 0
            else c.close
        )
        offset = vwap - c.close
        yield Candle(
            timestamp_ms=c.timestamp_ms,
            open=c.open + offset,
            high=c.high + offset,
            low=c.low + offset,
            close=vwap,
            volume=c.volume,
        )


def _vwap_arrays(
    candles_1h: List[Candle],
    h: np.ndarray, l: np.ndarray, c: np.ndarray, volume: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build VWAP-adjusted (h, l, c) arrays. Sessions reset at 00:00 UTC."""
    n_c = len(candles_1h)
    vwap_h = np.zeros(n_c, dtype=np.float64)
    vwap_l = np.zeros(n_c, dtype=np.float64)
    vwap_c = np.zeros(n_c, dtype=np.float64)
    sessions: dict = {}
    for idx in range(n_c):
        cand = candles_1h[idx]
        day_key = cand.timestamp_ms // 86_400_000
        if day_key not in sessions:
            sessions[day_key] = {"cum_pv": 0.0, "cum_vol": 0.0}
        typical = (h[idx] + l[idx] + c[idx]) / 3.0
        sessions[day_key]["cum_pv"]  += typical * volume[idx]
        sessions[day_key]["cum_vol"] += volume[idx]
        vwap = (
            sessions[day_key]["cum_pv"] / sessions[day_key]["cum_vol"]
            if sessions[day_key]["cum_vol"] > 0
            else c[idx]
        )
        offset = vwap - c[idx]
        vwap_h[idx] = h[idx] + offset
        vwap_l[idx] = l[idx] + offset
        vwap_c[idx] = vwap
    return vwap_h, vwap_l, vwap_c


# ── Result cache ─────────────────────────────────────────────────────────

_SIGNAL_CACHE: OrderedDict = OrderedDict()
_CACHE_LIMIT  = 50_000


def _neutral_result(close: float) -> SignalResult:
    """SignalResult used when the input window is too short for indicators."""
    return SignalResult(
        trend=0, all_green=False, all_red=False,
        green_arrow=False, red_arrow=False,
        st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
        close_1h=close, score_long=0.0, score_short=0.0,
    )


# ── Main entry ───────────────────────────────────────────────────────────

def compute_signal(
    candles_1h: List[Candle],
    st_threshold: int = 3,
    st_configs: Optional[List[Tuple[int, float]]] = None,
    thresholds: Optional[SignalThresholds] = None,
    regime_label: str = "",
) -> SignalResult:
    """
    Per-bar live signal compute.

    Args:
      candles_1h: chronological candle window. The latest bar is the one
                  being evaluated.
      st_threshold: count of agreeing STs to declare trend. 3 = unanimous,
                    2 = partial-alignment regimes.
      st_configs: optional override of [(period, multiplier), …] for the three
                  Supertrend channels. Default [(7,3.0), (14,2.0), (21,2.0)].
      thresholds: optional override of all confluence thresholds. Defaults to
                  the v4 baseline in `signal_weights.DEFAULT_THRESHOLDS`.
      regime_label: macro-regime name (e.g. "BULL_TREND"). When provided AND
                    `thresholds.use_regime_profiles` is True, the per-flag
                    weights are scaled by the regime profile. Passing the
                    empty string disables the regime adjustment.

    Returns: SignalResult with trend, arrows, flag values, signal_score, and
    signal_strength populated.
    """
    if len(candles_1h) < 30:
        return _neutral_result(candles_1h[-1].close if candles_1h else 0.0)

    cfg = thresholds or DEFAULT_THRESHOLDS
    cfg_tuple = tuple(st_configs) if st_configs is not None else None
    # Use weights tuple (not id(cfg)) to avoid memory-address collision across
    # object lifetimes. The other threshold fields almost never change between
    # calls so weights is the distinguishing factor.
    cfg_key = tuple(sorted(cfg.weights.items()))
    cache_key = (
        candles_1h[-1].timestamp_ms,
        candles_1h[-1].close,
        candles_1h[0].close,
        len(candles_1h),
        st_threshold,
        cfg_tuple,
        regime_label,
        cfg_key,
    )
    if cache_key in _SIGNAL_CACHE:
        _SIGNAL_CACHE.move_to_end(cache_key)
        return _SIGNAL_CACHE[cache_key]

    # ── OHLCV arrays ─────────────────────────────────────────────────────
    o = np.array([cd.open  for cd in candles_1h], dtype=np.float64)
    h = np.array([cd.high  for cd in candles_1h], dtype=np.float64)
    l = np.array([cd.low   for cd in candles_1h], dtype=np.float64)
    c = np.array([cd.close for cd in candles_1h], dtype=np.float64)
    volume = np.array([cd.volume for cd in candles_1h], dtype=np.float64)

    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)
    ha_bull_arr = ha_body_bull(o, h, l, c)

    _st_cfgs = st_configs if st_configs is not None else [(7, 3.0), (14, 2.0), (21, 2.0)]
    if len(_st_cfgs) != 3:
        raise ValueError(
            f"st_configs must have exactly 3 (period, multiplier) tuples, got {len(_st_cfgs)}"
        )
    p1, m1 = _st_cfgs[0]
    p2, m2 = _st_cfgs[1]
    p3, m3 = _st_cfgs[2]

    # ST1: Heikin-Ashi (smoothed). ST2: real candles. ST3: VWAP-adjusted.
    st1_line, st1_trend = compute_supertrend(ha_h, ha_l, ha_c, p1, m1)
    st2_line, st2_trend = compute_supertrend(h,    l,    c,    p2, m2)
    vwap_h, vwap_l, vwap_c = _vwap_arrays(candles_1h, h, l, c, volume)
    st3_line, st3_trend = compute_supertrend(vwap_h, vwap_l, vwap_c, p3, m3)

    st_trends_now  = (int(st1_trend[-1]), int(st2_trend[-1]), int(st3_trend[-1]))
    st_trends_prev = (
        int(st1_trend[-2]) if len(st1_trend) >= 2 else 0,
        int(st2_trend[-2]) if len(st2_trend) >= 2 else 0,
        int(st3_trend[-2]) if len(st3_trend) >= 2 else 0,
    )
    st_values_now = (float(st1_line[-1]), float(st2_line[-1]), float(st3_line[-1]))

    # ── Per-bar features ─────────────────────────────────────────────────
    flip = flip_state_at(st_trends_now, st_trends_prev, st_values_now, st_threshold)

    # Direction-correct score_long/score_short summaries — kept for
    # back-compat (UI widgets read these).
    green_count = sum(1 for t in st_trends_now if t == 1)
    red_count   = sum(1 for t in st_trends_now if t == -1)
    score_long  = round(green_count / 3.0 * 100.0, 2)
    score_short = round(red_count   / 3.0 * 100.0, 2)

    rsi_arr = compute_rsi(c, 14)
    cur_rsi = float(rsi_arr[-1])
    rsi_s = rsi_state_at(cur_rsi, flip.trend, cfg)

    # Squeeze on BB(20,2) inside KC(20,10,1.5) at i-1; breakout on i.
    if len(c) >= max(cfg.bb_period + 2, cfg.kc_period + 2):
        bb_lo, _bb_mid, bb_hi = bollinger_bands(c, cfg.bb_period, cfg.bb_std)
        kc_lo, _kc_mid, kc_hi = keltner(
            h, l, c, cfg.kc_period, cfg.kc_atr_period, cfg.kc_mult,
        )
        sq = squeeze_state_at(
            close_now=float(c[-1]),
            bb_lo_prev=float(bb_lo[-2]), bb_hi_prev=float(bb_hi[-2]),
            kc_lo_prev=float(kc_lo[-2]), kc_hi_prev=float(kc_hi[-2]),
            bb_lo_now=float(bb_lo[-1]),  bb_hi_now=float(bb_hi[-1]),
        )
    else:
        # Warmup window — no squeeze evaluation.
        from app.engines.directional.signal_features import SqueezeState
        sq = SqueezeState(False, False, False, False)

    # Volume spike on rolling-20 median window.
    vol_window = volume[-20:] if volume.size >= 20 else volume
    vol = volume_state_at(float(volume[-1]), vol_window, cfg)

    # HA alignment + HA/real divergence.
    ha = ha_state_at(
        ha_bull_now=bool(ha_bull_arr[-1]),
        ha_close_now=float(ha_c[-1]) if ha_c.size > 0 else float(c[-1]),
        real_close_now=float(c[-1]),
        trend=flip.trend,
        thresholds=cfg,
    )

    # CVD-proxy divergence.
    cvd = cvd_state_at(o, h, l, c, volume, flip.trend, cfg)

    # ATR percentile for volatility-adaptive staleness.
    atr_arr = compute_atr(h, l, c, 14)
    atr_pct = float(np.sum(atr_arr[-1] > atr_arr[-100:]) / min(100, len(atr_arr)) * 100.0) if len(atr_arr) >= 2 else 50.0

    # Staleness lookback (volatility-adaptive).
    bars_active = staleness_lookback_at(
        st1_trend, st2_trend, st3_trend, flip.trend, st_threshold, cfg,
        atr_percentile=atr_pct,
    )

    # Multi-TF boost: signal trend aligned with macro regime.
    mtf = mtf_boost_at(flip.trend, regime_label)

    # ── Score assembly ───────────────────────────────────────────────────
    signal_score, signal_strength, _earned, _tot = assemble_signal_score(
        flip=flip, rsi=rsi_s, sq=sq, vol=vol, ha=ha, cvd=cvd, mtf=mtf,
        bars_active=bars_active, thresholds=cfg, regime_label=regime_label,
    )

    res = SignalResult(
        trend=flip.trend,
        all_green=flip.all_green,
        all_red=flip.all_red,
        green_arrow=flip.green_arrow,
        red_arrow=flip.red_arrow,
        st_trends=list(flip.st_trends),
        st_values=list(flip.st_values),
        close_1h=float(c[-1]),
        score_long=score_long,
        score_short=score_short,
        signal_strength=signal_strength,
        signal_score=signal_score,
        rsi=round(rsi_s.rsi, 2),
        squeezed=sq.squeezed,
        ha_real_divergence_pct=round(ha.ha_real_div_pct, 4),
        vol_confirm=vol.vol_spike,
        bars_since_flip=bars_active,
        cvd_proxy=round(cvd.cvd_sum, 4),
    )

    if len(_SIGNAL_CACHE) >= _CACHE_LIMIT:
        _SIGNAL_CACHE.popitem(last=False)
    _SIGNAL_CACHE[cache_key] = res
    return res
