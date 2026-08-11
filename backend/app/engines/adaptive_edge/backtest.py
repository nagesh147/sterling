"""Deterministic historical replay for Adaptive Edge v0.1.0.

No broker/API calls occur here. The replay consumes a sequence of already
prepared MarketFeatures and prices, then applies the same reconstructed model
functions used by the strategy. It is research-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .model import (
    MarketFeatures,
    f101_feature_score,
    f102_edge_score,
    f103_opportunity,
    f104_dynamic_mode,
    f105_profit_protection,
    f106_dynamic_risk,
    f107_risk_per_unit,
    f110_entry_trigger,
    f111_exit_trigger,
    f112_protection_parameters,
)


@dataclass(frozen=True)
class ReplayBar:
    close: float
    spread_bps: float
    features: MarketFeatures
    atr: float


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


def _entry(bar: ReplayBar, direction: int, slippage_bps: float) -> float:
    half_spread = max(0.0, bar.close * bar.spread_bps / 20_000.0)
    slip = bar.close * slippage_bps / 10_000.0
    return bar.close + direction * (half_spread + slip)


def _exit(bar: ReplayBar, direction: int, slippage_bps: float) -> float:
    half_spread = max(0.0, bar.close * bar.spread_bps / 20_000.0)
    slip = bar.close * slippage_bps / 10_000.0
    return bar.close - direction * (half_spread + slip)


def _drawdown(equity: Sequence[float]) -> float:
    peak = 0.0
    result = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            result = max(result, (peak - value) / peak)
    return result


def _evaluate(bar: ReplayBar, execution_cost: float, base_risk: float, drawdown_ratio: float):
    feature_score = f101_feature_score(bar.features)
    edge_score = f102_edge_score(feature_score)
    opportunity = f103_opportunity(
        edge_score=edge_score,
        confidence=bar.features.confidence,
        expected_move=bar.features.expected_move,
        execution_cost=execution_cost,
    )
    mode = f104_dynamic_mode(
        edge_score=edge_score,
        confidence=bar.features.confidence,
        stale=bar.features.stale,
        late_session=bar.features.late_session,
    )
    return feature_score, edge_score, opportunity, mode


def run_replay(bars: Sequence[ReplayBar], config: ReplayConfig = ReplayConfig()) -> ReplayResult:
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

        bar = bars[i]
        execution_cost = bar.close * (config.fee_rate + config.slippage_bps / 10_000.0)
        _, edge_score, opportunity, mode = _evaluate(bar, execution_cost, capital * config.risk_fraction, 0.0)
        if not opportunity.eligible or opportunity.direction == 0:
            equity.append(capital)
            i += 1
            continue

        stop_price, _ = f112_protection_parameters(
            entry_price=bar.close,
            atr=max(bar.atr, bar.close * 0.001),
            edge_score=edge_score,
        )
        risk_per_unit = f107_risk_per_unit(
            entry_price=bar.close,
            stop_price=stop_price,
            point_value=1.0,
            estimated_cost=execution_cost,
        )
        risk = f106_dynamic_risk(
            base_risk=capital * config.risk_fraction,
            confidence=bar.features.confidence,
            volatility_ratio=max(1.0, bar.atr / max(bar.close * 0.01, 1e-9)),
            drawdown_ratio=_drawdown(equity),
        )
        if risk.authorized_risk <= 0 or risk_per_unit <= 0:
            equity.append(capital)
            i += 1
            continue

        option_score = 1.0
        if not f110_entry_trigger(opportunity=opportunity, mode=mode, option_score=option_score):
            equity.append(capital)
            i += 1
            continue

        quantity = risk.authorized_risk / risk_per_unit
        direction = opportunity.direction
        entry = _entry(bar, direction, config.slippage_bps)
        peak_pnl = 0.0
        exit_index = min(i + config.max_holding_bars, len(bars) - 1)
        exit_reason = "time"

        for j in range(i + 1, exit_index + 1):
            current = bars[j]
            current_pnl = (current.close - entry) * quantity * direction
            peak_pnl = max(peak_pnl, current_pnl)
            floor_pnl, _ = f105_profit_protection(peak_pnl=peak_pnl, current_pnl=current_pnl)
            _, next_edge, _, _ = _evaluate(current, execution_cost, risk.authorized_risk, 0.0)
            if f111_exit_trigger(
                direction=direction,
                edge_score=next_edge,
                current_pnl=current_pnl,
                protection_floor=floor_pnl,
            ):
                exit_index = j
                exit_reason = "edge_or_profit_protection"
                break

        exit_bar = bars[exit_index]
        exit_price = _exit(exit_bar, direction, config.slippage_bps)
        gross = (exit_price - entry) * quantity * direction
        notional = abs(entry * quantity) + abs(exit_price * quantity)
        costs = notional * config.fee_rate
        net = gross - costs
        capital = max(0.0, capital + net)
        equity.append(capital)
        trades.append(ReplayTrade(i, exit_index, direction, entry, exit_price, gross, costs, net, risk.authorized_risk, exit_reason))
        cooldown_until = exit_index + config.cooldown_bars
        i = exit_index + 1

    wins = sum(t.net_pnl > 0 for t in trades)
    gains = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    losses = -sum(t.net_pnl for t in trades if t.net_pnl < 0)
    return ReplayResult(
        initial_capital=config.initial_capital,
        final_capital=capital,
        trades=tuple(trades),
        equity_curve=tuple(equity),
        max_drawdown=_drawdown(equity),
        total_return=capital / config.initial_capital - 1.0 if config.initial_capital else 0.0,
        win_rate=wins / len(trades) if trades else 0.0,
        profit_factor=gains / losses if losses > 0 else None,
    )
