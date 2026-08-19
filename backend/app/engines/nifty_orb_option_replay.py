"""Historical option-premium replay for the NIFTY ORB strategy.

This module consumes normalized option bars and never substitutes underlying
points for option P&L. A replay entry must have at least one subsequent bar so
an entry cannot be exited against information from the same candle.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Literal, Sequence

Side = Literal["LONG", "SHORT"]

@dataclass(frozen=True)
class OptionBar:
    timestamp: datetime
    symbol: str
    option_type: Literal["CE", "PE"]
    strike: float
    expiry: str
    open: float
    high: float
    low: float
    close: float
    bid: float = 0.0
    ask: float = 0.0
    volume: float = 0.0
    open_interest: float = 0.0
    lot_size: int = 1

@dataclass(frozen=True)
class ReplayCostConfig:
    slippage_points: float = 0.0
    brokerage_per_order: float = 0.0
    charges_per_order: float = 0.0

@dataclass(frozen=True)
class ReplayTrade:
    symbol: str
    option_type: str
    strike: float
    expiry: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    gross_pnl: float
    costs: float
    net_pnl: float
    r_multiple: float
    exit_reason: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["entry_time"] = self.entry_time.isoformat()
        d["exit_time"] = self.exit_time.isoformat()
        return d


def executable_entry(bar: OptionBar, costs: ReplayCostConfig) -> float:
    """Use ask for a buy when available, otherwise close, plus slippage."""
    base = bar.ask if bar.ask > 0 else bar.close
    return base + max(costs.slippage_points, 0.0)


def executable_exit(bar: OptionBar, costs: ReplayCostConfig) -> float:
    """Use bid for a sell when available, otherwise close, minus slippage."""
    base = bar.bid if bar.bid > 0 else bar.close
    return max(0.0, base - max(costs.slippage_points, 0.0))


def replay_trade(
    bars: Sequence[OptionBar],
    entry_index: int,
    risk_points: float,
    target_r: float,
    costs: ReplayCostConfig = ReplayCostConfig(),
) -> ReplayTrade | None:
    # Entry must be followed by at least one later candle. Otherwise the previous
    # implementation used bars[-1] as the exit, which could equal the entry bar
    # and leak same-candle information into P&L.
    if entry_index < 0 or entry_index >= len(bars) - 1 or risk_points <= 0:
        return None
    entry_bar = bars[entry_index]
    entry = executable_entry(entry_bar, costs)
    if entry <= 0:
        return None
    stop = entry - risk_points
    target = entry + risk_points * target_r
    exit_bar = bars[-1]
    reason = "end_of_data"
    for bar in bars[entry_index + 1:]:
        # Conservative sequencing: if both stop and target occur in one bar,
        # assume the adverse stop happened first.
        if bar.low <= stop:
            exit_bar, reason = bar, "stop"
            break
        if bar.high >= target:
            exit_bar, reason = bar, "target"
            break
    exit_price = executable_exit(exit_bar, costs)
    quantity = max(1, entry_bar.lot_size)
    gross = (exit_price - entry) * quantity
    orders = 2
    trade_costs = orders * (costs.brokerage_per_order + costs.charges_per_order)
    net = gross - trade_costs
    return ReplayTrade(entry_bar.symbol, entry_bar.option_type, entry_bar.strike, entry_bar.expiry, entry_bar.timestamp, exit_bar.timestamp, entry, exit_price, quantity, gross, trade_costs, net, net / max(risk_points * quantity, 1e-9), reason)


def summarize_replay(trades: Sequence[ReplayTrade]) -> dict:
    if not trades:
        return {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "net_pnl": 0.0, "expectancy": 0.0, "max_drawdown": 0.0, "average_r": 0.0}
    pnl = [t.net_pnl for t in trades]
    wins = [x for x in pnl if x > 0]
    losses = [x for x in pnl if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = peak = 0.0
    max_dd = 0.0
    for x in pnl:
        equity += x
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "trades": len(trades), "wins": len(wins), "losses": len(losses),
        "win_rate": len(wins) / len(trades),
        "profit_factor": gross_profit / gross_loss if gross_loss else float("inf") if gross_profit else 0.0,
        "net_pnl": sum(pnl), "expectancy": sum(pnl) / len(pnl), "max_drawdown": max_dd,
        "average_r": sum(t.r_multiple for t in trades) / len(trades),
    }
