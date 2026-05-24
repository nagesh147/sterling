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
    # Regime risk adjustment (applied in HIGH_VOL)
    high_vol_risk_red: float = 1.0   # 0.5 = halve risk, 1.0 = no change


PROFILES = {
    # Hackathon demo — loose filters so signals fire immediately
    "demo_profile": VCPProfile(
        label="Demo Profile",
        signal_tf="15m",
        regime_tf="1h",
        signal_bar_ms=15 * 60_000,
        regime_bar_ms=60 * 60_000,
        hold_bars=8,
        direction="both",
        vol_filter_pct=5.0,
        flow_threshold=0.10,
        max_ibs_long=0.48,
        min_ibs_short=0.52,
        max_rsi_long=50.0,
        min_rsi_short=50.0,
        stop_mult=1.0,
        tp1_mult=1.8,
        tp2_mult=3.0,
        trail_mult=0.6,
        risk_pct=0.010,
        max_positions=2,
        high_vol_risk_red=1.0,
    ),
    # BTC profiles
    "btc_scalping_5m": VCPProfile(
        label="BTC Scalping 5m",
        signal_tf="5m", regime_tf="1h",
        signal_bar_ms=5 * 60_000,
        regime_bar_ms=60 * 60_000,
        hold_bars=12,
        direction="both",
        vol_filter_pct=35.0,
        flow_threshold=0.35,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=0.8,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.0035,
        max_positions=2,
        high_vol_risk_red=0.5,
    ),
    "btc_scalping_15m": VCPProfile(
        label="BTC Scalping 15m",
        signal_tf="15m", regime_tf="1h",
        signal_bar_ms=15 * 60_000,
        regime_bar_ms=60 * 60_000,
        hold_bars=12,
        direction="both",
        vol_filter_pct=35.0,
        flow_threshold=0.35,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=0.85,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.0045,
        max_positions=2,
        high_vol_risk_red=0.5,
    ),
    "btc_scalping_30m": VCPProfile(
        label="BTC Scalping 30m",
        signal_tf="30m", regime_tf="2h",
        signal_bar_ms=30 * 60_000,
        regime_bar_ms=2 * 60_60_000,
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
        high_vol_risk_red=0.75,
    ),
    "btc_intraday_1h": VCPProfile(
        label="BTC Intraday 1h",
        signal_tf="1h", regime_tf="4h",
        signal_bar_ms=60 * 60_000,
        regime_bar_ms=4 * 60 * 60_000,
        hold_bars=8,
        direction="both",
        vol_filter_pct=40.0,
        flow_threshold=0.30,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=1.0,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.006,
        max_positions=3,
        high_vol_risk_red=1.0,
    ),
    "btc_intraday_4h": VCPProfile(
        label="BTC Intraday 4h",
        signal_tf="4h", regime_tf="1d",
        signal_bar_ms=4 * 60 * 60_000,
        regime_bar_ms=24 * 60 * 60_000,
        hold_bars=6,
        direction="both",
        vol_filter_pct=45.0,
        flow_threshold=0.25,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=1.2,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.007,
        max_positions=4,
        high_vol_risk_red=1.0,
    ),
    # ETH profiles
    "eth_scalping_5m": VCPProfile(
        label="ETH Scalping 5m",
        signal_tf="5m", regime_tf="1h",
        signal_bar_ms=5 * 60_000,
        regime_bar_ms=60 * 60_000,
        hold_bars=12,
        direction="both",
        vol_filter_pct=35.0,
        flow_threshold=0.35,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=0.8,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.0035,
        max_positions=2,
        high_vol_risk_red=0.5,
    ),
    "eth_scalping_15m": VCPProfile(
        label="ETH Scalping 15m",
        signal_tf="15m", regime_tf="1h",
        signal_bar_ms=15 * 60_000,
        regime_bar_ms=60 * 60_000,
        hold_bars=12,
        direction="both",
        vol_filter_pct=35.0,
        flow_threshold=0.35,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=0.85,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.0045,
        max_positions=2,
        high_vol_risk_red=0.5,
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
        high_vol_risk_red=0.75,
    ),
    "eth_intraday_1h": VCPProfile(
        label="ETH Intraday 1h",
        signal_tf="1h", regime_tf="4h",
        signal_bar_ms=60 * 60_000,
        regime_bar_ms=4 * 60 * 60_000,
        hold_bars=8,
        direction="both",
        vol_filter_pct=40.0,
        flow_threshold=0.30,
        max_ibs_long=0.35,
        min_ibs_short=0.65,
        max_rsi_long=40.0,
        min_rsi_short=60.0,
        stop_mult=1.0,
        tp1_mult=1.5,
        trail_mult=0.5,
        risk_pct=0.006,
        max_positions=3,
        high_vol_risk_red=1.0,
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