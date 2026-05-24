"""STRATEGY STUB — Hybrid VCP-Momentum strategy removed in the strategy reset.

All decision logic (indicators, signals, entries, exits, microstructure,
executor, live feed, profiles) was stripped so a new strategy can be built on a
clean seam. The originals are preserved in git history on the `strategy-v2`
branch.

What remains here are thin stubs that keep the live-feed loop in `main.py` and
the VCP backtest endpoint importing cleanly and degrading to empty states:
  * `PROFILES` is empty  → no VCP live feeds start; the backtest endpoint
    returns "no valid profiles".
  * `VCPLiveFeed` / `VCPExecutor` are inert no-ops (never constructed at runtime
    because no profile is active).

Implement the new VCP strategy here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.engines.hybrid_vcp.backtest import (
    run_all_profiles,
    run_backtest,
    BacktestReport,
    Trade,
)

# No profiles → no feeds activate and the VCP backtest endpoint short-circuits.
PROFILES: Dict[str, "VCPProfile"] = {}


@dataclass
class VCPProfile:
    label: str = "stub"
    signal_tf: str = ""
    regime_tf: str = ""
    signal_bar_ms: int = 0
    vol_filter_pct: float = 0.0
    flow_threshold: float = 0.0
    max_ibs_long: float = 1.0
    min_ibs_short: float = 0.0
    max_rsi_long: float = 100.0
    min_rsi_short: float = 0.0


@dataclass
class VCPFeedConfig:
    exchange: str = ""
    symbols: List[str] = field(default_factory=list)
    signal_tf_secs: int = 60


@dataclass
class VCPExecutorConfig:
    vol_filter_pct: float = 0.0
    flow_threshold: float = 0.0
    max_ibs_long: float = 1.0
    min_ibs_short: float = 0.0
    max_rsi_long: float = 100.0
    min_rsi_short: float = 0.0


@dataclass
class VCPExecutorState:
    pass


class VCPExecutor:
    """Inert executor stub (no strategy loaded)."""

    def __init__(self, profile=None, router=None, adapter=None, config=None):
        self.profile = profile
        self.router = router
        self.adapter = adapter
        self.config = config
        self.state = VCPExecutorState()

    async def on_bar(self, *args: Any, **kwargs: Any) -> None:
        return None


class VCPLiveFeed:
    """Inert live-feed stub (no strategy loaded)."""

    def __init__(self, config=None, executor=None):
        self.config = config
        self.executor = executor

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


async def start_vcp_live_feed(*args: Any, **kwargs: Any) -> None:
    return None


__all__ = [
    "PROFILES",
    "VCPProfile",
    "VCPFeedConfig",
    "VCPExecutorConfig",
    "VCPExecutorState",
    "VCPExecutor",
    "VCPLiveFeed",
    "start_vcp_live_feed",
    "run_all_profiles",
    "run_backtest",
    "BacktestReport",
    "Trade",
]
