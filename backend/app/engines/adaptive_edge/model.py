"""Pure mathematical model for Adaptive Edge v0.1.0.

This is a reconstructed baseline, not a recovered historical specification.
Every function is deterministic and independent of broker/execution I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import floor, tanh
from typing import Mapping

from .contracts import DynamicMode
from .edge import EdgeAssessment
from .feature_engine import FeatureSnapshot
from .formula_registry import require_implemented


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class MarketFeatures:
    trend: float
    momentum: float
    relative_volume: float
    volatility_expansion: float
    expected_move: float
    confidence: float
    stale: bool = False
    late_session: bool = False


@dataclass(frozen=True)
class Opportunity:
    eligible: bool
    direction: int
    edge_score: float
    confidence: float
    expected_gross_value: float
    reason: str


@dataclass(frozen=True)
class RiskSchedule:
    authorized_risk: float
    multiplier: float
    reason: str


@dataclass(frozen=True)
class OptionCandidate:
    symbol: str
    delta: float
    spread_pct: float
    relative_volume: float
    theta_pct: float
    liquidity_score: float


@dataclass(frozen=True)
class OptionSelection:
    symbol: str | None
    score: float


@dataclass(frozen=True)
class ProtectionState:
    peak_pnl: float
    floor_pnl: float
    giveback: float
    stop_price: float
    target_price: float


def f101_feature_score(features: MarketFeatures) -> float:
    """F-101: weighted directional feature score in [-1, 1]."""
    require_implemented("F-101")
    trend = clip(features.trend, -1.0, 1.0)
    momentum = clip(features.momentum, -1.0, 1.0)
    volume = clip(features.relative_volume, -1.0, 1.0)
    volatility = clip(features.volatility_expansion, -1.0, 1.0)
    return clip(0.35 * trend + 0.30 * momentum + 0.20 * volume + 0.15 * volatility, -1.0, 1.0)


def f102_edge_score(feature_score: float) -> float:
    """F-102: smooth the composite signal while preserving direction."""
    require_implemented("F-102")
    return tanh(2.0 * clip(feature_score, -1.0, 1.0))


def f103_opportunity(
    *,
    edge_score: float,
    confidence: float,
    expected_move: float,
    execution_cost: float,
    minimum_edge: float = 0.60,
) -> Opportunity:
    """F-103: require directional edge, confidence and positive economics."""
    require_implemented("F-103")
    gross = abs(edge_score) * max(expected_move, 0.0)
    eligible = (
        abs(edge_score) >= minimum_edge
        and confidence >= 0.55
        and gross > execution_cost
    )
    if abs(edge_score) < minimum_edge:
        reason = "edge_below_threshold"
    elif confidence < 0.55:
        reason = "confidence_below_threshold"
    elif gross <= execution_cost:
        reason = "economics_negative"
    else:
        reason = "eligible"
    return Opportunity(eligible, 1 if edge_score > 0 else -1, edge_score, confidence, gross, reason)


def f104_dynamic_mode(
    *,
    edge_score: float,
    confidence: float,
    stale: bool,
    late_session: bool,
) -> DynamicMode:
    """F-104: behavior state; never changes risk authorization."""
    require_implemented("F-104")
    if stale:
        return DynamicMode.HALTED
    if late_session:
        return DynamicMode.EXIT_ONLY
    strength = abs(edge_score) * confidence
    if strength >= 0.48:
        return DynamicMode.INTRADAY
    if strength >= 0.25:
        return DynamicMode.ACTIVE
    if strength >= 0.12:
        return DynamicMode.DEFENSIVE
    return DynamicMode.OBSERVE


def f105_profit_protection(
    *,
    peak_pnl: float,
    current_pnl: float,
    giveback_fraction: float = 0.35,
) -> tuple[float, float]:
    """F-105: protect a fraction of peak realized/unrealized profit."""
    require_implemented("F-105")
    giveback = max(peak_pnl - current_pnl, 0.0)
    floor_pnl = max(0.0, peak_pnl * (1.0 - clip(giveback_fraction, 0.0, 1.0)))
    return floor_pnl, giveback


def f106_dynamic_risk(
    *,
    base_risk: float,
    confidence: float,
    volatility_ratio: float,
    drawdown_ratio: float,
) -> RiskSchedule:
    """F-106: risk changes from risk inputs, not from DynamicMode."""
    require_implemented("F-106")
    confidence_factor = clip(confidence, 0.0, 1.0)
    volatility_factor = 1.0 / max(volatility_ratio, 1.0)
    drawdown_factor = clip(1.0 - max(drawdown_ratio, 0.0), 0.0, 1.0)
    multiplier = clip(confidence_factor * volatility_factor * drawdown_factor, 0.0, 1.0)
    return RiskSchedule(max(base_risk, 0.0) * multiplier, multiplier, "confidence*volatility^-1*drawdown")


def f107_risk_per_unit(
    *,
    entry_price: float,
    stop_price: float,
    point_value: float,
    estimated_cost: float,
) -> float:
    """F-107: monetary loss to stop for one unit, including execution cost."""
    require_implemented("F-107")
    if entry_price <= 0 or point_value <= 0:
        raise ValueError("entry_price and point_value must be positive")
    distance = abs(entry_price - stop_price)
    return distance * point_value + max(estimated_cost, 0.0)


def f108_position_size(*, authorized_risk: float, risk_per_unit: float, lot_size: int) -> int:
    """F-108: floor risk budget to whole lots."""
    require_implemented("F-108")
    if lot_size <= 0:
        raise ValueError("lot_size must be positive")
    if risk_per_unit <= 0 or authorized_risk <= 0:
        return 0
    units = floor(authorized_risk / risk_per_unit)
    return (units // lot_size) * lot_size


def f109_option_selection(candidates: tuple[OptionCandidate, ...], direction: int) -> OptionSelection:
    """F-109: prefer liquid near-target-delta contracts with low spread/theta."""
    require_implemented("F-109")
    if not candidates:
        return OptionSelection(None, 0.0)
    target_delta = 0.55
    best = max(
        candidates,
        key=lambda c: (
            0.40 * (1.0 - abs(abs(c.delta) - target_delta) / target_delta)
            + 0.30 * clip(c.liquidity_score, 0.0, 1.0)
            + 0.20 * clip(c.relative_volume, 0.0, 2.0) / 2.0
            - 0.07 * clip(c.spread_pct, 0.0, 1.0)
            - 0.03 * clip(c.theta_pct, 0.0, 1.0)
        ),
    )
    score = (
        0.40 * (1.0 - abs(abs(best.delta) - target_delta) / target_delta)
        + 0.30 * clip(best.liquidity_score, 0.0, 1.0)
        + 0.20 * clip(best.relative_volume, 0.0, 2.0) / 2.0
        - 0.07 * clip(best.spread_pct, 0.0, 1.0)
        - 0.03 * clip(best.theta_pct, 0.0, 1.0)
    )
    return OptionSelection(best.symbol, clip(score, 0.0, 1.0))


def f110_entry_trigger(*, opportunity: Opportunity, mode: DynamicMode, option_score: float) -> bool:
    """F-110: entry requires economic eligibility, active behavior and liquid instrument."""
    require_implemented("F-110")
    return opportunity.eligible and mode in (DynamicMode.ACTIVE, DynamicMode.INTRADAY) and option_score >= 0.60


def f111_exit_trigger(*, direction: int, edge_score: float, current_pnl: float, protection_floor: float) -> bool:
    """F-111: exit on edge reversal or protected-profit breach."""
    require_implemented("F-111")
    reversed_edge = edge_score * direction <= -0.10
    protected_profit_breach = current_pnl < protection_floor
    return reversed_edge or protected_profit_breach


def f112_protection_parameters(
    *,
    entry_price: float,
    atr: float,
    edge_score: float,
) -> tuple[float, float]:
    """F-112: adaptive stop/target distance from ATR and edge strength."""
    require_implemented("F-112")
    if entry_price <= 0 or atr <= 0:
        raise ValueError("entry_price and atr must be positive")
    strength = clip(abs(edge_score), 0.0, 1.0)
    stop_distance = atr * (1.50 - 0.50 * strength)
    target_distance = atr * (2.00 + 1.00 * strength)
    return entry_price - stop_distance, entry_price + target_distance


def f113_reentry_trigger(
    *,
    was_exited: bool,
    fresh_edge_score: float,
    prior_edge_score: float,
    cooldown_elapsed: bool,
) -> bool:
    """F-113: require a fresh strengthening edge after a completed exit."""
    require_implemented("F-113")
    return was_exited and cooldown_elapsed and abs(fresh_edge_score) >= 0.60 and abs(fresh_edge_score) > abs(prior_edge_score)


def f114_position_interaction(*, existing_risk: float, new_risk: float, total_risk_budget: float, correlation_penalty: float = 0.0) -> float:
    """F-114: cap aggregate risk after a portfolio concentration penalty."""
    require_implemented("F-114")
    penalty = clip(correlation_penalty, 0.0, 1.0)
    available = max(total_risk_budget - existing_risk, 0.0) * (1.0 - penalty)
    return min(max(new_risk, 0.0), available)


def evaluate_reconstructed_model(
    *,
    features: MarketFeatures,
    execution_cost: float,
    opportunity_id: str,
) -> EdgeAssessment:
    """Produce an EdgeAssessment using F-101/F-102 only."""
    feature_score = f101_feature_score(features)
    edge_score = f102_edge_score(feature_score)
    gross = abs(edge_score) * max(features.expected_move, 0.0)
    return EdgeAssessment(
        opportunity_id=opportunity_id,
        score=edge_score,
        confidence=clip(features.confidence, 0.0, 1.0),
        expected_gross_value=gross,
        formula_id="F-102",
        formula_version="0.1.0",
        inputs={
            "feature_score": feature_score,
            "expected_move": features.expected_move,
            "execution_cost": execution_cost,
        },
    )
