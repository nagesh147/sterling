"""STRATEGY STUB — Hybrid VCP backtest removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. `run_all_profiles` /
`run_backtest` return empty results so the VCP backtest endpoint degrades to an
empty state. (With `PROFILES` empty the endpoint short-circuits before calling
these, but they are kept for import compatibility.)

Implement the new VCP backtest here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Trade:
    entry_ts: int = 0
    exit_ts: int = 0
    direction: str = ""
    entry: float = 0.0
    exit: float = 0.0
    pnl: float = 0.0
    reason: str = ""


@dataclass
class BacktestReport:
    profile: str = ""
    trade_count: int = 0
    win_rate: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    total_return: float = 0.0
    trades: List[Trade] = field(default_factory=list)


def run_backtest(*args: Any, **kwargs: Any) -> BacktestReport:
    return BacktestReport()


def run_all_profiles(
    candles_by_tf: Dict[str, Any], profiles: Dict[str, Any]
) -> Dict[str, BacktestReport]:
    return {}
