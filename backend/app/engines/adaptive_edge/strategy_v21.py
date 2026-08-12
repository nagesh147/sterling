"""Adaptive Edge V2.1 proposed strategy definition.

This module is the explicit new-definition path required by A26-RA after
repository recovery found no authoritative complete F-101..F-114 definitions.
It therefore does not claim to recover the old strategy. It defines a complete,
parameterized, causal V2.1 strategy that can be researched and validated.

All numerical values live in StrategyParameters so research configuration is
never hidden in formula code. The production execution gate additionally
requires explicit promotion approval; implementation is not promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, floor, isfinite, tanh
from typing import Mapping, Sequence


class StrategyDefinitionError(ValueError):
    pass


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


class OperatingMode(str, Enum):
    NORMAL = "NORMAL"
    RESTRICTED = "RESTRICTED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class StrategyParameters:
    """Explicit research parameters for Adaptive Edge V2.1.

    Defaults are a deterministic research configuration, not production truth.
    Every value is versioned with the strategy definition and must be validated
    out of sample before promotion.
    """

    version: str = "2.1.0-proposed"
    horizon_bars: int = 15
    feature_means: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0)
    feature_scales: tuple[float, ...] = (1.0, 1.0, 1.0, 1.0)
    feature_weights: tuple[float, ...] = (1.0, 1.0, 1.0, 1.0)
    edge_threshold: float = 0.15
    minimum_expected_net_value: float = 0.0
    restricted_volatility_ratio: float = 1.5
    disabled_volatility_ratio: float = 2.5
    restricted_drawdown_fraction: float = 0.03
    disabled_drawdown_fraction: float = 0.05
    normal_risk_multiplier: float = 1.0
    restricted_risk_multiplier: float = 0.5
    disabled_risk_multiplier: float = 0.0
    maximum_risk: float = 1.0
    edge_risk_floor: float = 0.25
    edge_risk_ceiling: float = 1.0
    minimum_risk_per_unit: float = 1e-9
    contract_multiplier: float = 1.0
    quantity_increment: int = 1
    minimum_quantity: int = 0
    maximum_quantity: int = 1_000_000
    initial_stop_distance: float = 1.0
    profit_lock_fraction: float = 0.5
    target_multiple: float = 2.0
    maximum_reentries: int = 0
    reentry_cooldown_bars: int = 1
    maximum_positions: int = 1
    portfolio_risk_fraction: float = 1.0

    def __post_init__(self) -> None:
        if self.horizon_bars <= 0:
            raise StrategyDefinitionError("horizon_bars must be positive")
        if not (len(self.feature_means) == len(self.feature_scales) == len(self.feature_weights)):
            raise StrategyDefinitionError("feature parameter dimensions must match")
        if not self.feature_weights or sum(abs(w) for w in self.feature_weights) <= 0:
            raise StrategyDefinitionError("feature weights must contain non-zero mass")
        if any(not isfinite(x) for x in (*self.feature_means, *self.feature_scales, *self.feature_weights)):
            raise StrategyDefinitionError("feature parameters must be finite")
        if any(scale <= 0 for scale in self.feature_scales):
            raise StrategyDefinitionError("feature scales must be positive")
        if not 0 <= self.edge_threshold <= 1:
            raise StrategyDefinitionError("edge_threshold must be in [0, 1]")
        if self.disabled_volatility_ratio < self.restricted_volatility_ratio:
            raise StrategyDefinitionError("disabled volatility threshold must be >= restricted threshold")
        if self.disabled_drawdown_fraction < self.restricted_drawdown_fraction:
            raise StrategyDefinitionError("disabled drawdown threshold must be >= restricted threshold")
        if not 0 <= self.restricted_risk_multiplier <= self.normal_risk_multiplier:
            raise StrategyDefinitionError("restricted risk multiplier must not exceed normal multiplier")
        if not 0 <= self.disabled_risk_multiplier <= self.restricted_risk_multiplier:
            raise StrategyDefinitionError("disabled risk multiplier must not exceed restricted multiplier")
        if self.maximum_risk < 0 or self.minimum_risk_per_unit <= 0:
            raise StrategyDefinitionError("risk limits are invalid")
        if self.contract_multiplier <= 0:
            raise StrategyDefinitionError("contract_multiplier must be positive")
        if self.quantity_increment <= 0 or self.minimum_quantity < 0 or self.maximum_quantity < self.minimum_quantity:
            raise StrategyDefinitionError("quantity constraints are invalid")
        if self.initial_stop_distance <= 0 or not 0 <= self.profit_lock_fraction <= 1:
            raise StrategyDefinitionError("protection parameters are invalid")
        if self.target_multiple <= 0:
            raise StrategyDefinitionError("target_multiple must be positive")
        if self.maximum_reentries < 0 or self.reentry_cooldown_bars < 0:
            raise StrategyDefinitionError("re-entry parameters are invalid")
        if self.maximum_positions <= 0 or not 0 <= self.portfolio_risk_fraction <= 1:
            raise StrategyDefinitionError("portfolio constraints are invalid")


@dataclass(frozen=True)
class EdgeAssessment:
    score: float
    direction: Direction | None
    p_up: float
    p_down: float
    p_neutral: float


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ProtectionParameters:
    initial_stop_distance: float
    target_distance: float
    profit_lock_fraction: float


@dataclass(frozen=True)
class PositionSize:
    quantity: int
    risk_per_unit: float
    authorized_risk: float


@dataclass(frozen=True)
class ReentryDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class PortfolioDecision:
    allowed: bool
    aggregate_risk: float
    reason: str


@dataclass(frozen=True)
class OptionCandidate:
    instrument_id: str
    option_type: str
    expected_net_value: float
    entry_price: float
    stop_price: float
    contract_multiplier: float
    quantity_increment: int
    minimum_quantity: int
    maximum_quantity: int
    liquidity_ok: bool = True
    slippage_ok: bool = True
    data_quality_ok: bool = True

    def __post_init__(self) -> None:
        if self.option_type not in {"CE", "PE"}:
            raise StrategyDefinitionError("option_type must be CE or PE")
        if self.entry_price <= 0 or self.contract_multiplier <= 0:
            raise StrategyDefinitionError("candidate price and multiplier must be positive")
        if self.quantity_increment <= 0 or self.minimum_quantity < 0 or self.maximum_quantity < self.minimum_quantity:
            raise StrategyDefinitionError("candidate quantity constraints are invalid")


def f101_feature_score(features: Sequence[float], p: StrategyParameters) -> float:
    """F-101: weighted normalized composite score bounded to [-1, 1]."""
    if len(features) != len(p.feature_weights):
        raise StrategyDefinitionError("feature dimension does not match strategy parameters")
    z = [(x - mean) / scale for x, mean, scale in zip(features, p.feature_means, p.feature_scales)]
    denominator = sum(abs(w) for w in p.feature_weights)
    return tanh(sum(w * x for w, x in zip(p.feature_weights, z)) / denominator)


def f102_edge_score(features: Sequence[float], p: StrategyParameters) -> EdgeAssessment:
    """F-102: map the F-101 score to a three-state directional probability."""
    score = f101_feature_score(features, p)
    logits = (score, -score, 0.0)
    pivot = max(logits)
    weights = [exp(value - pivot) for value in logits]
    total = sum(weights)
    probabilities = tuple(weight / total for weight in weights)
    p_up, p_down, p_neutral = probabilities
    edge = p_up - p_down
    direction = Direction.UP if edge >= p.edge_threshold else Direction.DOWN if edge <= -p.edge_threshold else None
    return EdgeAssessment(edge, direction, p_up, p_down, p_neutral)


def f103_opportunity_eligibility(
    edge: EdgeAssessment,
    expected_net_value: float,
    *,
    data_quality_ok: bool,
    mode: OperatingMode,
    p: StrategyParameters,
) -> EligibilityResult:
    """F-103: causal eligibility from prediction, economics, data quality and mode."""
    reasons: list[str] = []
    if edge.direction is None:
        reasons.append("edge_below_threshold")
    if expected_net_value < p.minimum_expected_net_value:
        reasons.append("expected_net_value_below_threshold")
    if not data_quality_ok:
        reasons.append("data_quality_invalid")
    if mode is OperatingMode.DISABLED:
        reasons.append("mode_disabled")
    return EligibilityResult(not reasons, tuple(reasons))


def f104_dynamic_mode(*, volatility_ratio: float, drawdown_fraction: float, data_quality_ok: bool, p: StrategyParameters) -> OperatingMode:
    """F-104: deterministic mode state machine with explicit thresholds."""
    if not isfinite(volatility_ratio) or not isfinite(drawdown_fraction):
        raise StrategyDefinitionError("mode inputs must be finite")
    if not data_quality_ok or volatility_ratio >= p.disabled_volatility_ratio or drawdown_fraction >= p.disabled_drawdown_fraction:
        return OperatingMode.DISABLED
    if volatility_ratio >= p.restricted_volatility_ratio or drawdown_fraction >= p.restricted_drawdown_fraction:
        return OperatingMode.RESTRICTED
    return OperatingMode.NORMAL


def f105_profit_protection(
    *,
    direction: Direction,
    entry_price: float,
    favorable_extreme: float,
    previous_stop: float | None,
    p: StrategyParameters,
) -> float:
    """F-105: monotonic profit-protection stop from a favorable extreme."""
    if entry_price <= 0 or favorable_extreme <= 0:
        raise StrategyDefinitionError("protection prices must be positive")
    initial_stop = entry_price - p.initial_stop_distance if direction is Direction.UP else entry_price + p.initial_stop_distance
    if direction is Direction.UP:
        candidate = entry_price + (favorable_extreme - entry_price) * p.profit_lock_fraction - p.initial_stop_distance
        stop = max(initial_stop, candidate)
        return max(stop, previous_stop) if previous_stop is not None else stop
    candidate = entry_price - (entry_price - favorable_extreme) * p.profit_lock_fraction + p.initial_stop_distance
    stop = min(initial_stop, candidate)
    return min(stop, previous_stop) if previous_stop is not None else stop


def f106_dynamic_risk(*, authorized_base_risk: float, edge_strength: float, mode: OperatingMode, p: StrategyParameters) -> float:
    """F-106: explicit risk schedule, capped and never negative."""
    if authorized_base_risk < 0 or not 0 <= edge_strength <= 1:
        raise StrategyDefinitionError("invalid dynamic-risk inputs")
    mode_multiplier = {
        OperatingMode.NORMAL: p.normal_risk_multiplier,
        OperatingMode.RESTRICTED: p.restricted_risk_multiplier,
        OperatingMode.DISABLED: p.disabled_risk_multiplier,
    }[mode]
    strength = max(p.edge_risk_floor, min(p.edge_risk_ceiling, edge_strength))
    return min(p.maximum_risk, authorized_base_risk * mode_multiplier * strength)


def f107_risk_per_unit(*, entry_price: float, protection_price: float, contract_multiplier: float, entry_cost_per_unit: float = 0.0, exit_cost_per_unit: float = 0.0, p: StrategyParameters) -> float:
    """F-107: worst-case planned protection loss plus explicit costs per unit."""
    if entry_price <= 0 or protection_price <= 0 or contract_multiplier <= 0:
        raise StrategyDefinitionError("risk inputs must be positive")
    costs = entry_cost_per_unit + exit_cost_per_unit
    if costs < 0:
        raise StrategyDefinitionError("execution costs cannot be negative")
    risk = abs(entry_price - protection_price) * contract_multiplier + costs * contract_multiplier
    return max(risk, p.minimum_risk_per_unit)


def f108_position_sizing(*, authorized_risk: float, risk_per_unit: float, quantity_increment: int, minimum_quantity: int, maximum_quantity: int) -> PositionSize:
    """F-108: floor quantity to contract increment without exceeding authorization."""
    if authorized_risk < 0 or risk_per_unit <= 0:
        raise StrategyDefinitionError("invalid sizing inputs")
    if quantity_increment <= 0 or minimum_quantity < 0 or maximum_quantity < minimum_quantity:
        raise StrategyDefinitionError("invalid quantity constraints")
    raw = floor(authorized_risk / risk_per_unit)
    quantity = (raw // quantity_increment) * quantity_increment
    quantity = min(quantity, maximum_quantity)
    if quantity < minimum_quantity:
        quantity = 0
    return PositionSize(quantity, risk_per_unit, authorized_risk)


def f109_instrument_selection(candidates: Sequence[OptionCandidate], direction: Direction) -> OptionCandidate | None:
    """F-109: select the highest-value valid directional option candidate."""
    expected_type = "CE" if direction is Direction.UP else "PE"
    valid = [
        candidate
        for candidate in candidates
        if candidate.option_type == expected_type
        and candidate.liquidity_ok
        and candidate.slippage_ok
        and candidate.data_quality_ok
    ]
    return max(valid, key=lambda candidate: (candidate.expected_net_value, candidate.instrument_id), default=None)


def f110_entry_trigger(*, direction: Direction, underlying_price: float, trigger_price: float) -> bool:
    """F-110: directional trigger against an explicit decision-time reference."""
    if underlying_price <= 0 or trigger_price <= 0:
        raise StrategyDefinitionError("trigger prices must be positive")
    return underlying_price >= trigger_price if direction is Direction.UP else underlying_price <= trigger_price


def f111_exit_trigger(*, direction: Direction, current_price: float, stop_price: float, target_price: float, horizon_expired: bool) -> bool:
    """F-111: protection, target, or explicit horizon exit."""
    if min(current_price, stop_price, target_price) <= 0:
        raise StrategyDefinitionError("exit prices must be positive")
    protection = current_price <= stop_price if direction is Direction.UP else current_price >= stop_price
    target = current_price >= target_price if direction is Direction.UP else current_price <= target_price
    return protection or target or horizon_expired


def f112_protection_parameters(*, direction: Direction, entry_price: float, p: StrategyParameters) -> ProtectionParameters:
    """F-112: derive explicit initial protection and target distances."""
    if entry_price <= 0:
        raise StrategyDefinitionError("entry_price must be positive")
    return ProtectionParameters(
        initial_stop_distance=p.initial_stop_distance,
        target_distance=p.initial_stop_distance * p.target_multiple,
        profit_lock_fraction=p.profit_lock_fraction,
    )


def f113_reentry(*, prior_exit_bar: int, current_bar: int, reentry_count: int, new_opportunity: bool, p: StrategyParameters) -> ReentryDecision:
    """F-113: explicit cooldown/count/new-opportunity re-entry rule."""
    if reentry_count < 0 or prior_exit_bar > current_bar:
        raise StrategyDefinitionError("invalid re-entry state")
    if reentry_count >= p.maximum_reentries:
        return ReentryDecision(False, "reentry_limit_reached")
    if current_bar - prior_exit_bar < p.reentry_cooldown_bars:
        return ReentryDecision(False, "reentry_cooldown")
    if not new_opportunity:
        return ReentryDecision(False, "no_new_opportunity")
    return ReentryDecision(True, "reentry_allowed")


def f114_multi_position_interaction(*, existing_positions: int, existing_risk: float, candidate_risk: float, p: StrategyParameters) -> PortfolioDecision:
    """F-114: explicit count and shared-risk-capacity constraint."""
    if existing_positions < 0 or existing_risk < 0 or candidate_risk < 0:
        raise StrategyDefinitionError("portfolio inputs cannot be negative")
    if existing_positions >= p.maximum_positions:
        return PortfolioDecision(False, existing_risk, "maximum_positions_reached")
    aggregate = existing_risk + candidate_risk
    capacity = p.maximum_risk * p.portfolio_risk_fraction
    if aggregate > capacity:
        return PortfolioDecision(False, aggregate, "portfolio_risk_capacity_exceeded")
    return PortfolioDecision(True, aggregate, "portfolio_capacity_available")
