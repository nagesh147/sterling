"""Deterministic replay harness for the reconstructed Adaptive Edge model.

This deliberately accepts precomputed causal features rather than fetching
market data. A data adapter can feed the same rows in backtest or paper mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .model import MarketFeatures, f102_edge_score, f101_feature_score, f103_opportunity


@dataclass(frozen=True)
class ReplayBar:
    timestamp: str
    features: MarketFeatures
    execution_cost: float


@dataclass(frozen=True)
class ReplayDecision:
    timestamp: str
    edge_score: float
    expected_gross_value: float
    eligible: bool
    reason: str


@dataclass(frozen=True)
class ReplayReport:
    bars: int
    eligible_bars: int
    mean_edge: float
    total_expected_net_value: float


def replay(bars: Iterable[ReplayBar]) -> tuple[tuple[ReplayDecision, ...], ReplayReport]:
    decisions: list[ReplayDecision] = []
    net_values: list[float] = []
    edge_values: list[float] = []

    for bar in bars:
        feature_score = f101_feature_score(bar.features)
        edge_score = f102_edge_score(feature_score)
        opportunity = f103_opportunity(
            edge_score=edge_score,
            confidence=bar.features.confidence,
            expected_move=bar.features.expected_move,
            execution_cost=bar.execution_cost,
        )
        net_value = opportunity.expected_gross_value - bar.execution_cost
        edge_values.append(edge_score)
        net_values.append(net_value if opportunity.eligible else 0.0)
        decisions.append(
            ReplayDecision(
                timestamp=bar.timestamp,
                edge_score=edge_score,
                expected_gross_value=opportunity.expected_gross_value,
                eligible=opportunity.eligible,
                reason=opportunity.reason,
            )
        )

    count = len(decisions)
    eligible_count = sum(1 for decision in decisions if decision.eligible)
    report = ReplayReport(
        bars=count,
        eligible_bars=eligible_count,
        mean_edge=(sum(edge_values) / count) if count else 0.0,
        total_expected_net_value=sum(net_values),
    )
    return tuple(decisions), report
