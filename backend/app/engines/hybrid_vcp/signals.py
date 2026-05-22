"""
Hybrid VCP-Momentum Scalper — Strategy V2
Hybrid entry signal logic: mode detection + COMPRESSION/EXPANSION signals.

Entry path: indicators.Bundle + microstructure → hybrid_signal → entry_triggered
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.hybrid_vcp.indicators import (
    IndicatorBundle,
    VCPConfig,
    MomentumConfig,
    ATRConfig,
    compute_atr,
    compute_rsi,
    compute_ema,
    compute_vol_sma,
    compute_ibs,
    compute_pivot_high,
    compute_pivot_low,
    compute_bb,
    bb_width_percentile,
    atr_percentile,
)
from app.engines.hybrid_vcp.microstructure import (
    obi_proxy,
    cvd_proxy,
    cvd_proxy_bar,
    flow_score,
    detect_divergence,
    micro_confirmation_at,
    MicroConfirmation,
)


# ──────────────────────────────────────────────────────────────────────────────
# Mode
# ──────────────────────────────────────────────────────────────────────────────

class VolMode(str, Enum):
    COMPRESSION = "COMPRESSION"
    EXPANSION   = "EXPANSION"


@dataclass(frozen=True)
class ModeState:
    mode:            VolMode
    bb_width_pct:    float   # 0-100
    atr_pct:         float   # 0-100


def detect_mode(
    closes: NDArray[np.float64],
    highs:  NDArray[np.float64],
    lows:   NDArray[np.float64],
    atr:    NDArray[np.float64],
    vc:     Optional[VCPConfig] = None,
) -> VolMode:
    """
    Detect COMPRESSION vs EXPANSION based on BB width percentile.

    BB width < 30th percentile → COMPRESSION (favor mean-reversion)
    BB width ≥ 30th percentile → EXPANSION   (favor momentum breakout)
    """
    cfg = vc or VCPConfig()
    bw_pct = bb_width_percentile(
        closes,
        lookback=cfg.bb_width_pct_lookback,
        period=cfg.bb_period,
        std_mult=cfg.bb_std,
    )
    if bw_pct < cfg.compression_threshold_pct:
        return VolMode.COMPRESSION
    return VolMode.EXPANSION


class Regime(str, Enum):
    BULL     = "bull"      # Uptrend, price above quantile(0.7)
    CHOP     = "chop"      # Tight range + low volume
    BEAR     = "bear"      # Downtrend, price below quantile(0.3)
    NEUTRAL  = "neutral"   # Between BULL and BEAR
    HIGH_VOL = "high_vol" # ATR elevated — reduce risk


def detect_regime(
    closes:    NDArray[np.float64],
    highs:     NDArray[np.float64],
    lows:      NDArray[np.float64],
    atr:       NDArray[np.float64],
    volume:    NDArray[np.float64],
    idx:       int,
    lookback:  int = 60,
) -> Regime:
    """
    Multi-factor regime detector using price trend, ATR ratio, and volume.

    Returns one of: BULL | CHOP | BEAR | NEUTRAL | HIGH_VOL

    Regime logic (applied to prefix[:idx+1]):
    - HIGH_VOL : atr_ratio > 1.8  (current ATR 1.8× its lookback mean)
    - CHOP     : price_range < 0.018 AND vol_ratio < 0.7
    - BULL     : price > SMA AND price > quantile(0.7)
    - BEAR     : price < SMA AND price < quantile(0.3)
    - NEUTRAL  : the rest
    """
    if idx < lookback or idx < 20:
        return Regime.NEUTRAL

    _cl = closes[:idx+1]
    _hi = highs[:idx+1]
    _lo = lows[:idx+1]
    _at = atr[:idx+1]
    _vl = volume[:idx+1]

    window_cl = _cl[-lookback:]
    window_at = _at[-lookback:]
    window_vl = _vl[-lookback:]

    # HIGH_VOL — skip or reduce size
    atr_ratio = float(_at[idx] / (np.nanmean(window_at) + 1e-9))
    if atr_ratio > 1.8:
        return Regime.HIGH_VOL

    price_range = float((np.nanmax(window_cl) - np.nanmin(window_cl)) / (_cl[0] + 1e-9))
    vol_ratio   = float(_vl[idx] / (np.nanmean(window_vl) + 1e-9))

    # CHOP — tight range + low volume
    if price_range < 0.018 and vol_ratio < 0.7:
        return Regime.CHOP

    sma  = float(np.nanmean(window_cl))
    q70  = float(np.nanpercentile(window_cl, 70))
    q30  = float(np.nanpercentile(window_cl, 30))
    price = float(_cl[idx])

    if price > sma and price > q70:
        return Regime.BULL
    elif price < sma and price < q30:
        return Regime.BEAR

    return Regime.NEUTRAL


# ──────────────────────────────────────────────────────────────────────────────
# Hybrid Signal
# ──────────────────────────────────────────────────────────────────────────────

class Direction(int, Enum):
    LONG  = +1
    SHORT = -1
    NONE  =  0


@dataclass(frozen=True)
class HybridSignal:
    direction:       Direction
    mode:            VolMode
    reason:          str
    entry_score:     float          # 0-1 confidence
    microstructure: Optional[MicroConfirmation] = None


def signal_compression(
    ibs:        NDArray[np.float64],
    rsi:        NDArray[np.float64],
    vc:         Optional[VCPConfig] = None,
) -> NDArray[np.int8]:
    """
    COMPRESSION mode: mean-reversion entry signals.
    LONG  = IBS ≤ 0.35 AND RSI ≤ 40
    SHORT = IBS ≥ 0.65 AND RSI ≥ 60
    0 = no signal, 1 = long, -1 = short
    """
    n = len(ibs)
    signals = np.zeros(n, dtype=np.int8)
    for i in range(1, n):
        ib = float(ibs[i])
        rs = float(rsi[i])
        if ib <= 0.35 and rs <= 40.0:
            signals[i] = 1
        elif ib >= 0.65 and rs >= 60.0:
            signals[i] = -1
    return signals


def signal_breakout(
    closes:    NDArray[np.float64],
    highs:     NDArray[np.float64],
    lows:      NDArray[np.float64],
    rsi:       NDArray[np.float64],
    ema8:      NDArray[np.float64],
    ema21:     NDArray[np.float64],
    pivot_high: NDArray[np.float64],
    pivot_low:  NDArray[np.float64],
    volume:    NDArray[np.float64],
    vol_sma20: NDArray[np.float64],
    mc:        Optional[MomentumConfig] = None,
) -> NDArray[np.int8]:
    """
    EXPANSION mode: momentum breakout signals.
    LONG  = price breaks pivot_high AND EMA8 > EMA21 AND RSI crosses above 52
            AND volume > 1.25 × vol_sma
    SHORT = mirror
    0 = no signal, 1 = long, -1 = short
    """
    cfg = mc or MomentumConfig()
    n = len(closes)
    signals = np.zeros(n, dtype=np.int8)

    for i in range(1, n):
        price = float(closes[i])
        ph    = float(pivot_high[i])
        pl    = float(pivot_low[i])
        e8    = float(ema8[i])
        e21   = float(ema21[i])
        rs    = float(rsi[i])
        rs_p  = float(rsi[i - 1])
        vol   = float(volume[i])
        vsma  = float(vol_sma20[i])

        # Volume check
        if vsma > 0 and vol < cfg.volume_spike_mult * vsma:
            continue

        # EMA alignment
        if e8 <= e21:
            continue

        # RSI cross above 52 for long
        if rs > cfg.rsi_breakout_long and rs_p <= cfg.rsi_breakout_long and price > ph:
            signals[i] = 1
        # RSI cross below 48 for short
        elif rs < cfg.rsi_breakout_short and rs_p >= cfg.rsi_breakout_short and price < pl:
            signals[i] = -1

    return signals


# ──────────────────────────────────────────────────────────────────────────────
# Full hybrid signal per bar
# ──────────────────────────────────────────────────────────────────────────────

def compute_hybrid_signal(
    bundle:     IndicatorBundle,
    opens:      NDArray[np.float64],
    highs:      NDArray[np.float64],
    lows:       NDArray[np.float64],
    closes:     NDArray[np.float64],
    volume:     NDArray[np.float64],
    vc:         Optional[VCPConfig]        = None,
    mc:         Optional[MomentumConfig]   = None,
    ac:         Optional[ATRConfig]         = None,
) -> tuple[VolMode, NDArray[np.int8], NDArray[np.int8]]:
    """
    Compute both compression and breakout signals + mode, per bar.

    Returns (mode, compression_signals, breakout_signals)
    compression_signals[i] = +1 long, -1 short, 0 none
    breakout_signals[i]     = +1 long, -1 short, 0 none
    """
    cfg_vc = vc or VCPConfig()
    cfg_mc = mc or MomentumConfig()
    cfg_ac = ac or ATRConfig()

    mode = detect_mode(closes, highs, lows, bundle.atr, cfg_vc)

    comp = signal_compression(bundle.ibs, bundle.rsi, cfg_vc)
    brk  = signal_breakout(
        closes, highs, lows,
        bundle.rsi, bundle.ema8, bundle.ema21,
        bundle.pivot_high, bundle.pivot_low,
        volume, bundle.vol_sma20,
        cfg_mc,
    )

    return mode, comp, brk


def hybrid_signal_at(
    idx:         int,
    mode:        VolMode,
    comp:        NDArray[np.int8],
    brk:         NDArray[np.int8],
    closes:      NDArray[np.float64],
    highs:       NDArray[np.float64],
    lows:       NDArray[np.float64],
    volume:     NDArray[np.float64],
    bundle:     IndicatorBundle,
    obi_arr:    NDArray[np.float64],
    cvd_bar_arr: NDArray[np.float64],
    cvd_cum:     NDArray[np.float64],
    atr:        NDArray[np.float64],
    flow_thresh: float = 0.35,
) -> HybridSignal:
    """
    Per-bar entry signal with full gate chain evaluated.

    Entry priority: Vol filter → Mode → Hybrid signal → Microstructure → Activity
    """
    n = len(closes)
    if idx < 1 or idx >= n:
        return HybridSignal(Direction.NONE, mode, "no_bars", 0.0)

    cfg_ac = ATRConfig()
    vol_pct = atr_percentile(atr, cfg_ac.atr_pct_lookback)

    # 1. Volatility filter
    if vol_pct <= cfg_ac.vol_filter_threshold:
        return HybridSignal(Direction.NONE, mode, "vol_filter_fail", 0.0)

    # 2. Activity filter — skip dead bars
    vol_sma = bundle.vol_sma20[idx]
    if vol_sma > 0 and float(volume[idx]) < 0.5 * vol_sma:
        return HybridSignal(Direction.NONE, mode, "low_activity", 0.0)

    # 3. Hybrid signal
    if mode == VolMode.COMPRESSION:
        raw_dir = int(comp[idx])
        reason  = "compression_reversion"
    else:
        raw_dir = int(brk[idx])
        reason  = "expansion_breakout"

    if raw_dir == 0:
        return HybridSignal(Direction.NONE, mode, "no_signal", 0.0)

    direction = Direction.LONG if raw_dir == 1 else Direction.SHORT

    # 4. Microstructure confirmation
    micro = micro_confirmation_at(
        obi_arr, cvd_bar_arr, cvd_cum,
        closes, raw_dir, flow_thresh=flow_thresh,
    )

    if micro.has_divergence:
        return HybridSignal(
            direction, mode,
            f"{reason}:divergence_detected",
            0.0, micro,
        )

    if micro.flow_score < flow_thresh:
        return HybridSignal(
            direction, mode,
            f"{reason}:flow_score_low({micro.flow_score:.2f}<{flow_thresh})",
            0.0, micro,
        )

    return HybridSignal(
        direction=direction,
        mode=mode,
        reason=reason,
        entry_score=micro.flow_score,
        microstructure=micro,
    )