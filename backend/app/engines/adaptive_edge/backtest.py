"""Deterministic historical replay for Adaptive Edge v0.1.0.

The replay engine is deliberately independent of broker/API code. It consumes
already-fetched Kite candles and evaluates the same model functions used by the
strategy. It models conservative executable references, costs, and non-overlap
without making live orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .model import AdaptiveEdgeModel, Bar, Opportunity


@dataclass(frozen=True)
class ReplayConfig:
    initial_capital: float = 100_000.0
    risk_fraction: float = 0.01
    fee_rate: float = 0.001
    slippage_bps: float = 5.0
    max_holding_bars: int = 24
    cooldown_bars: int = 2


@dataclass(frozen=True)
class ReplayTrade:
    entry_index: int
    exit_index: int
    direction: int
    entry_price: float
    exit_price: float
    gross_pnl: float
    costs: float
    net_pnl: float
    risk_budget: float
    exit_reason: str


@dataclass(frozen=True)
class ReplayResult:
    initial_capital: float
    final_capital: float
    trades: tuple[ReplayTrade, ...]
    equity_curve: tuple[float, ...]
    max_drawdown: float
    total_return: float
    win_rate: float
    profit_factor: float | None


def _executable_entry(bar: Bar, direction: int, slippage_bps: float) -> float:
    # Longs cross the ask; shorts cross the bid. The Bar model exposes a spread
    # estimate, so we apply half-spread plus explicit adverse slippage.
    half_spread = max(0.0, bar.close * bar.spread_bps / 20_000.0)
    slip = bar.close * slippage_bps / 10_000.0
    return bar.close + direction * (half_spread + slip)


def _executable_exit(bar: Bar, direction: int, slippage_bps: float) -> float:
    half_spread = max(0.0, bar.close * bar.spread_bps / 20_000.0)
    slip = bar.close * slippage_bps / 10_000.0
    return bar.close - direction * (half_spread + slip)


def _drawdown(equity: Sequence[float]) -> float:
    peak = float("-inf")
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)
    return max_dd


def run_replay(
    bars: Sequence[Bar],
    model: AdaptiveEdgeModel,
    config: ReplayConfig = ReplayConfig(),
) -> ReplayResult:
    capital = config.initial_capital
    equity = [capital]
    trades: list[ReplayTrade] = []
    cooldown_until = -1
    i = 0

    while i < len(bars):
        if i < cooldown_until:
            equity.append(capital)
            i += 1
            continue

        opportunity: Opportunity | None = model.evaluate(bars, i)
        if opportunity is None or opportunity.direction == 0:
            equity.append(capital)
            i += 1
            continue

        direction = opportunity.direction
        entry = _executable_entry(bars[i], direction, config.slippage_bps)
        risk_budget = capital * config.risk_fraction
        risk_per_unit = max(opportunity.risk_per_unit, 1e-9)
        quantity = risk_budget / risk_per_unit
        if quantity <= 0:
            equity.append(capital)
            i += 1
            continue

        exit_index = min(i + config.max_holding_bars, len(bars) - 1)
        exit_reason = "time"
        for j in range(i + 1, exit_index + 1):
            decision = model.evaluate(bars, j)
            if decision is None or decision.direction != direction:
                exit_index = j
                exit_reason = "edge_invalidated"
                break
            if decision.protection_triggered:
                exit_index = j
                exit_reason = "profit_protection"
                break

        exit_price = _executable_exit(bars[exit_index], direction, config.slippage_bps)
        gross = (exit_price - entry) * quantity * direction
        notional = (abs(entry * quantity) + abs(exit_price * quantity))
        costs = notional * config.fee_rate
        net = gross - costs
        capital = max(0.0, capital + net)
        equity.append(capital)
        trades.append(
            ReplayTrade(
                entry_index=i,
                exit_index=exit_index,
                direction=direction,
                entry_price=entry,
                exit_price=exit_price,
                gross_pnl=gross,
                costs=costs,
                net_pnl=net,
                risk_budget=risk_budget,
                exit_reason=exit_reason,
            )
        )
        cooldown_until = exit_index + config.cooldown_bars
        i = exit_index + 1

    wins = sum(1 for t in trades if t.net_pnl > 0)
    gains = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    losses = -sum(t.net_pnl for t in trades if t.net_pnl < 0)
    return ReplayResult(
        initial_capital=config.initial_capital,
        final_capital=capital,
        trades=tuple(trades),
        equity_curve=tuple(equity),
        max_drawdown=_drawdown(equity),
        total_return=(capital / config.initial_capital - 1.0) if config.initial_capital else 0.0,
        win_rate=(wins / len(trades)) if trades else 0.0,
        profit_factor=(gains / losses) if losses > 0 else None,
    )
