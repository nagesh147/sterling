"""
Hybrid VCP-Momentum Scalper — Strategy V2
Entry signal composition — combines all gates into a final entry trigger.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.hybrid_vcp.indicators import (
    IndicatorBundle, VCPConfig, MomentumConfig, ATRConfig,
)
from app.engines.hybrid_vcp.microstructure import (
    obi_proxy, cvd_proxy, cvd_proxy_bar, micro_confirmation_at, MicroConfirmation,
)
from app.engines.hybrid_vcp.signals import (
    detect_mode, signal_compression, signal_breakout,
    hybrid_signal_at, HybridSignal, VolMode, Direction,
    compute_hybrid_signal,
)


@dataclass(frozen=True)
class EntryGate:
    triggered:       bool
    direction:       Direction
    reason:          str
    entry_score:     float
    microstructure: Optional[MicroConfirmation]
    mode:            VolMode
    entry_price:     Optional[float]  # next-bar open, set by backtest


@dataclass(frozen=True)
class EntryConfig:
    """Configurable entry gates."""
    vol_filter_pct:    float = 35.0   # ATR percentile must exceed this
    flow_threshold:  float = 0.35    # minimum microstructure flow score
    min_ibs_long:     float = 0.0    # IBS floor for long (0.0 = no floor)
    max_ibs_long:     float = 0.35    # IBS ceiling for long
    min_ibs_short:    float = 0.65    # IBS floor for short
    max_ibs_short:    float = 1.0    # IBS ceiling for short
    min_rsi_long:    float = 0.0    # RSI floor for long
    max_rsi_long:     float = 40.0   # RSI ceiling for long
    min_rsi_short:   float = 60.0   # RSI floor for short
    max_rsi_short:    float = 100.0  # RSI ceiling for short
    ibs_lookback:     int = 1       # use current bar IBS (0=prev bar)


def evaluate_gate(
    idx:         int,
    closes:      NDArray[np.float64],
    highs:      NDArray[np.float64],
    lows:       NDArray[np.float64],
    opens:      NDArray[np.float64],
    volume:     NDArray[np.float64],
    bundle:     IndicatorBundle,
    vc:         Optional[VCPConfig]  = None,
    mc:         Optional[MomentumConfig] = None,
    ac:         Optional[ATRConfig]  = None,
    config:     Optional[EntryConfig] = None,
) -> EntryGate:
    """
    Full entry gate evaluation at bar index `idx`.

    Evaluates in order: volatility → mode → IBS/RSI compression →
    EMA/RSI breakout → microstructure → activity.
    """
    cfg  = config  or EntryConfig()
    cfg_vc = vc    or VCPConfig()
    cfg_mc = mc    or MomentumConfig()
    cfg_ac = ac    or ATRConfig()
    n = len(closes)

    if idx < 1 or idx >= n:
        return EntryGate(False, Direction.NONE, "no_bars", 0.0, None, VolMode.EXPANSION, None)

    # ── Precompute arrays ─────────────────────────────────────────
    obi_arr    = obi_proxy(highs, lows, closes, volume, bundle.vol_sma20)
    cvd_bar_arr = cvd_proxy_bar(opens, highs, lows, closes, volume)
    cvd_cum    = cvd_proxy(opens, highs, lows, closes, volume)
    # Per-bar mode: use prefix arrays so BB width reflects only available data.
    # This prevents look-ahead bias where future bars inflate BB width and
    # artificially push the mode toward EXPANSION.
    # Minimum 20 bars needed for BB period; fall back to EXPANSION if insufficient.
    if idx + 1 < 20:
        mode = VolMode.EXPANSION
    else:
        mode = detect_mode(closes[:idx+1], highs[:idx+1], lows[:idx+1],
                           bundle.atr[:idx+1], cfg_vc)
    comp       = signal_compression(bundle.ibs, bundle.rsi, cfg_vc)
    brk        = signal_breakout(
        closes, highs, lows, bundle.rsi, bundle.ema8, bundle.ema21,
        bundle.pivot_high, bundle.pivot_low, volume, bundle.vol_sma20, cfg_mc,
    )

    # ── 1. Volatility filter ─────────────────────────────────────
    from app.engines.hybrid_vcp.indicators import atr_percentile
    vol_pct = atr_percentile(bundle.atr, cfg_ac.atr_pct_lookback)
    if vol_pct <= cfg.vol_filter_pct:
        return EntryGate(False, Direction.NONE, "vol_filter_fail", 0.0, None, mode, None)

    # ── 2. Activity filter ──────────────────────────────────────
    vsma = float(bundle.vol_sma20[idx])
    vol  = float(volume[idx])
    if vsma > 0 and vol < 0.5 * vsma:
        return EntryGate(False, Direction.NONE, "low_activity", 0.0, None, mode, None)

    # ── 3. Signal ────────────────────────────────────────────────
    if mode == VolMode.COMPRESSION:
        raw_dir = int(comp[idx])
        reason  = "compression_reversion"
    else:
        raw_dir = int(brk[idx])
        reason  = "expansion_breakout"

    if raw_dir == 0:
        return EntryGate(False, Direction.NONE, "no_signal", 0.0, None, mode, None)

    direction = Direction.LONG if raw_dir == 1 else Direction.SHORT

    # ── 4. Compression-specific IBS/RSI gates ───────────────────
    if mode == VolMode.COMPRESSION:
        ib = float(bundle.ibs[idx])
        rs = float(bundle.rsi[idx])
        if raw_dir == 1:   # long
            if not (cfg.min_ibs_long <= ib <= cfg.max_ibs_long):
                return EntryGate(False, direction, f"ibs_oob({ib:.2f})", 0.0, None, mode, None)
            if not (cfg.min_rsi_long <= rs <= cfg.max_rsi_long):
                return EntryGate(False, direction, f"rsi_oob({rs:.1f})", 0.0, None, mode, None)
        else:              # short
            if not (cfg.min_ibs_short <= ib <= cfg.max_ibs_short):
                return EntryGate(False, direction, f"ibs_oob({ib:.2f})", 0.0, None, mode, None)
            if not (cfg.min_rsi_short <= rs <= cfg.max_rsi_short):
                return EntryGate(False, direction, f"rsi_oob({rs:.1f})", 0.0, None, mode, None)

    # ── 5. Microstructure ───────────────────────────────────────
    micro = micro_confirmation_at(
        obi_arr, cvd_bar_arr, cvd_cum,
        closes, raw_dir, idx,
        flow_thresh=cfg.flow_threshold,
    )

    if micro.has_divergence:
        return EntryGate(False, direction, f"divergence", 0.0, micro, mode, None)

    if micro.flow_score < cfg.flow_threshold:
        return EntryGate(False, direction, f"flow_low({micro.flow_score:.2f})", 0.0, micro, mode, None)

    return EntryGate(
        triggered=True,
        direction=direction,
        reason=reason,
        entry_score=float(micro.flow_score),
        microstructure=micro,
        mode=mode,
        entry_price=None,   # filled by backtest
    )