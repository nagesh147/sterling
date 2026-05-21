"""
Hybrid VCP-Momentum Scalper — Strategy V2
Strategy profiles for BTC and ETH across multiple timeframes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from app.engines.hybrid_vcp.exits import ExitConfig


@dataclass(frozen=True)
class VCPProfile:
    label:           str
    signal_tf:       str
    regime_tf:       str
    signal_bar_ms:   int
    regime_bar_ms:   int
    hold_bars:       int
    direction:       Literal["long", "short", "both"] = "both"
    # Vol filter (ATR percentile threshold)
    vol_filter_pct:  float = 35.0
    # Microstructure flow threshold
    flow_threshold:  float = 0.35
    # Entry IBS/RSI for compression mode
    max_ibs_long:    float = 0.35
    min_ibs_short:   float = 0.65
    max_rsi_long:    float = 40.0
    min_rsi_short:   float = 60.0
    # Exit
    stop_mult:       float = 0.9
    tp1_mult:        float = 1.5
    tp2_mult:        float = 2.5
    trail_mult:       float = 0.5
    # Risk
    risk_pct:         float = 0.005   # 0.5% equity per trade
    max_positions:   int   = 2


PROFILES = {
    "btc_scalping_15m": VCPProfile(
        label="BTC Scalping 15m",
        signal_tf="15m", regime_tf="1h",
        signal_bar_ms=15 * 60_000,
        regime_bar_ms=60 * 60_000,
        hold_bars=16,
        direction="both",
        vol_filter_pct=35.0,
        flow_threshold=0.35,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=0.9,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.005,
        max_positions=2,
    ),
    "btc_scalping_30m": VCPProfile(
        label="BTC Scalping 30m",
        signal_tf="30m", regime_tf="2h",
        signal_bar_ms=30 * 60_000,
        regime_bar_ms=2 * 60 * 60_000,
        hold_bars=12,
        direction="both",
        vol_filter_pct=35.0,
        flow_threshold=0.35,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=0.9,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.005,
        max_positions=2,
    ),
    "eth_scalping_15m": VCPProfile(
        label="ETH Scalping 15m",
        signal_tf="15m", regime_tf="1h",
        signal_bar_ms=15 * 60_000,
        regime_bar_ms=60 * 60_000,
        hold_bars=16,
        direction="both",
        vol_filter_pct=35.0,
        flow_threshold=0.35,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=0.9,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.005,
        max_positions=2,
    ),
    "eth_scalping_30m": VCPProfile(
        label="ETH Scalping 30m",
        signal_tf="30m", regime_tf="2h",
        signal_bar_ms=30 * 60_000,
        regime_bar_ms=2 * 60 * 60_000,
        hold_bars=12,
        direction="both",
        vol_filter_pct=35.0,
        flow_threshold=0.35,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=0.9,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.005,
        max_positions=2,
    ),
}


def exit_config_from_profile(profile: VCPProfile) -> ExitConfig:
    return ExitConfig(
        stop_mult=profile.stop_mult,
        tp1_mult=profile.tp1_mult,
        tp2_mult=profile.tp2_mult,
        trail_mult=profile.trail_mult,
        hold_bars=profile.hold_bars,
    )