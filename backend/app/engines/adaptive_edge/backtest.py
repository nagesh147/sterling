"""Research-only deterministic replay for the canonical Adaptive Edge model.

This module deliberately does not contain strategy formulas. It consumes
causally prepared observations and a caller-supplied model decision. That
separation prevents the backtester from silently becoming a second strategy
implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from .canonical_math import ExecutionCost, monotonic_stop, position_size, risk_per_unit


@dataclass(frozen=True)
class ReplayObservation:
    """One decision-time observation with causally available market values."""

    timestamp: str
    close: float
    bid: float
    ask: float
    initial_stop: float
    point_value: float
    lot_size: int


@dataclass(frozen=True)
class ReplayDecision:
    """Immutable decision supplied by the canonical strategy pipeline."""

    direction: int
    authorized_risk: float
    stop_price: float
    target_price: float | None = None


@dataclass(frozen=True)
class ReplayTrade:
    entry_index: int
    exit_index: int
    direction: int
    quantity: int
    entry_price: float
    exit_price: float
    gross_pnl: float
    costs: float
    net_pnl: float
    authorized_risk: float
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


def _drawdown(equity: Sequence[float]) -> float:
    peak = 0.0
    result = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            result = max(result, (peak - value) / peak)
    return result


def _execution_cost(observation: ReplayObservation, *, fee_rate: float, slippage_bps: float) -> ExecutionCost:
    half_spread = max(observation.ask - observation.bid, 0.0) / 2.0
    slippage = observation.close * max(slippage_bps, 0.0) / 10_000.0
    fees = observation.close * max(fee_rate, 0.0)
    return ExecutionCost(spread=half_spread, slippage=slippage, brokerage=fees)


def run_replay(
    observations: Sequence[ReplayObservation],
    decision_fn: Callable[[ReplayObservation, float], ReplayDecision | None],
    *,
    initial_capital: float = 100_000.0,
    fee_rate: float = 0.001,
    slippage_bps: float = 5.0,
    max_holding_bars: int = 24,
) -> ReplayResult:
    """Replay a precomputed decision function without creating strategy logic.

    ``decision_fn`` receives only the current observation and current capital.
    Future observations are never exposed to it.
    """
    if initial_capital < 0 or max_holding_bars < 1:
        raise ValueError("invalid replay configuration")

    capital = initial_capital
    equity = [capital]
    trades: list[ReplayTrade] = []
    i = 0

    while i < len(observations):
        observation = observations[i]
        decision = decision_fn(observation, capital)
        if decision is None or decision.direction not in (-1, 1):
            equity.append(capital)
            i += 1
            continue

        unit_risk = risk_per_unit(
            observation.close,
            decision.stop_price,
            observation.point_value,
            _execution_cost(observation, fee_rate=fee_rate, slippage_bps=slippage_bps).total,
        )
        quantity = position_size(decision.authorized_risk, unit_risk, observation.lot_size)
        if quantity <= 0:
            equity.append(capital)
            i += 1
            continue

        entry = observation.ask if decision.direction > 0 else observation.bid
        exit_index = min(i + max_holding_bars, len(observations) - 1)
        exit_reason = "time"
        active_stop = decision.stop_price

        for j in range(i + 1, exit_index + 1):
            current = observations[j]
            if decision.direction > 0:
                active_stop = monotonic_stop(active_stop, min(current.close, current.close))
                if current.close <= active_stop:
                    exit_index = j
                    exit_reason = "stop"
                    break
                if decision.target_price is not None and current.close >= decision.target_price:
                    exit_index = j
                    exit_reason = "target"
                    break
            else:
                if current.close >= active_stop:
                    exit_index = j
                    exit_reason = "stop"
                    break
                if decision.target_price is not None and current.close <= decision.target_price:
                    exit_index = j
                    exit_reason = "target"
                    break

        exit_observation = observations[exit_index]
        exit_price = exit_observation.bid if decision.direction > 0 else exit_observation.ask
        gross = (exit_price - entry) * quantity * decision.direction
        entry_cost = _execution_cost(observation, fee_rate=fee_rate, slippage_bps=slippage_bps).total * quantity
        exit_cost = _execution_cost(exit_observation, fee_rate=fee_rate, slippage_bps=slippage_bps).total * quantity
        costs = entry_cost + exit_cost
        net = gross - costs
        capital = max(0.0, capital + net)
        equity.append(capital)
        trades.append(
            ReplayTrade(
                i,
                exit_index,
                decision.direction,
                quantity,
                entry,
                exit_price,
                gross,
                costs,
                net,
                decision.authorized_risk,
                exit_reason,
            )
        )
        i = exit_index + 1

    wins = sum(trade.net_pnl > 0 for trade in trades)
    gains = sum(trade.net_pnl for trade in trades if trade.net_pnl > 0)
    losses = -sum(trade.net_pnl for trade in trades if trade.net_pnl < 0)
    return ReplayResult(
        initial_capital=initial_capital,
        final_capital=capital,
        trades=tuple(trades),
        equity_curve=tuple(equity),
        max_drawdown=_drawdown(equity),
        total_return=(capital / initial_capital - 1.0) if initial_capital else 0.0,
        win_rate=wins / len(trades) if trades else 0.0,
        profit_factor=gains / losses if losses else None,
    )
