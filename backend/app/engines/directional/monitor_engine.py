"""STRATEGY STUB — open-position exit monitoring removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. `check_exits` never signals
an exit so existing positions are left untouched by strategy logic.

Implement the new exit-monitoring logic here.
"""
from __future__ import annotations

from typing import Optional

from app.schemas.risk import ExitSignal


def check_exits(
    sized_trade,
    signal,
    current_pnl_usd: float,
    dte_remaining: int,
    current_spot: float = 0.0,
    current_tp: Optional[float] = None,
    current_sl: Optional[float] = None,
    force_exit_dte: int = 3,
    financial_stop_pct: float = 0.50,
    partial_profit_r1: float = 1.5,
    partial_profit_r2: float = 2.0,
) -> ExitSignal:
    """Neutral: never exit (no strategy loaded)."""
    return ExitSignal(should_exit=False, reason="strategy removed — no exit logic")
