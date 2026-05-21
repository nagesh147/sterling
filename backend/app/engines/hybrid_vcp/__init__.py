"""
Hybrid VCP-Momentum Scalper — Strategy V2
Engine modules: indicators, signals, microstructure, entries, exits,
backtest, profiles, live_filters.
"""
from app.engines.hybrid_vcp.indicators   import compute_bundle, IndicatorBundle
from app.engines.hybrid_vcp.signals     import Direction, detect_mode, signal_compression, signal_breakout
from app.engines.hybrid_vcp.entries     import EntryConfig, EntryGate, evaluate_gate
from app.engines.hybrid_vcp.exits      import ExitConfig, ExitResult, ExitReason, PositionState, check_exits
from app.engines.hybrid_vcp.microstructure import obi_proxy, cvd_proxy, cvd_proxy_bar, flow_score, detect_divergence
from app.engines.hybrid_vcp.profiles   import VCPProfile, PROFILES, exit_config_from_profile
from app.engines.hybrid_vcp.backtest   import run_backtest, run_all_profiles, BacktestReport, Trade
from app.engines.hybrid_vcp.live_filters import (
    LiveMicroState, LiveFilterConfig, LiveFilterDecision,
    evaluate_live_filters, obi_from_orderbook, cvd_from_trades,
)
from app.engines.hybrid_vcp.executor import VCPExecutor, VCPExecutorConfig, VCPExecutorState
from app.engines.hybrid_vcp.live_feed import VCPLiveFeed, VCPFeedConfig, start_vcp_live_feed

__all__ = [
    # Indicators
    "compute_bundle", "IndicatorBundle",
    # Signals
    "Direction", "detect_mode", "signal_compression", "signal_breakout",
    # Entries
    "EntryConfig", "evaluate_gate", "GateDecision",
    # Exits
    "ExitConfig", "ExitResult", "ExitReason", "PositionState", "check_exits",
    # Microstructure
    "obi_proxy", "cvd_proxy", "cvd_proxy_bar", "flow_score", "detect_divergence",
    # Profiles
    "VCPProfile", "PROFILES", "exit_config_from_profile",
    # Backtest
    "run_backtest", "run_all_profiles", "BacktestReport", "Trade",
    # Live filters
    "LiveMicroState", "LiveFilterConfig", "LiveFilterDecision",
    "evaluate_live_filters", "obi_from_orderbook", "cvd_from_trades",
    # Executor
    "VCPExecutor", "VCPExecutorConfig", "VCPExecutorState",
    # Live feed
    "VCPLiveFeed", "VCPFeedConfig", "start_vcp_live_feed",
]