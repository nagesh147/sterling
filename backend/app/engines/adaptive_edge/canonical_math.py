"""Source-derived Adaptive Edge mathematical operators.

Every operator in this module corresponds to a relationship explicitly stated
by the Master Mathematical Specification. Learned/validated quantities remain
inputs; this module does not invent their values.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, floor, log, sqrt
from typing import Sequence


def mid(bid: float, ask: float) -> float:
    if bid <= 0 or ask <= 0 or bid > ask:
        raise ValueError("invalid bid/ask")
    return (bid + ask) / 2.0


def spread(bid: float, ask: float) -> float:
    if bid <= 0 or ask <= 0 or bid > ask:
        raise ValueError("invalid bid/ask")
    return ask - bid


def relative_spread(bid: float, ask: float) -> float:
    return spread(bid, ask) / mid(bid, ask)


def price_change(current: float, previous: float) -> float:
    if previous <= 0:
        raise ValueError("previous price must be positive")
    return current - previous


def return_(current: float, previous: float) -> float:
    return price_change(current, previous) / previous


def velocity(change: float, delta_t: float) -> float:
    if delta_t <= 0:
        raise ValueError("delta_t must be positive")
    return change / delta_t


def acceleration(delta_velocity: float, delta_t: float) -> float:
    if delta_t <= 0:
        raise ValueError("delta_t must be positive")
    return delta_velocity / delta_t


def incremental_volume(ttq: float, previous_ttq: float) -> float | None:
    value = ttq - previous_ttq
    return None if value < 0 else value


def aggressor(trade_price: float, bid: float, ask: float) -> str:
    if bid <= 0 or ask <= 0 or bid > ask:
        raise ValueError("invalid quote")
    if trade_price >= ask:
        return "BUY"
    if trade_price <= bid:
        return "SELL"
    return "UNKNOWN"


def delta(aggressive_buy_volume: float, aggressive_sell_volume: float) -> float:
    return aggressive_buy_volume - aggressive_sell_volume


def cumulative_delta(previous: float, interval_delta: float) -> float:
    return previous + interval_delta


def liquidity_imbalance(bid_qty: float, ask_qty: float) -> float | None:
    denominator = bid_qty + ask_qty
    if denominator <= 0:
        return None
    return (bid_qty - ask_qty) / denominator


def volume_intensity(current_volume_rate: float, expected_volume_rate: float) -> float:
    if expected_volume_rate <= 0:
        raise ValueError("expected_volume_rate must be positive")
    return current_volume_rate / expected_volume_rate


def normalized_return(future_return: float, sigma: float) -> float:
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    return future_return / sigma


def multinomial_logistic(scores: Sequence[float], coefficients: Sequence[Sequence[float]], intercepts: Sequence[float] | None = None) -> tuple[float, ...]:
    if not coefficients:
        raise ValueError("at least one class is required")
    if any(len(row) != len(scores) for row in coefficients):
        raise ValueError("coefficient dimensions do not match scores")
    offsets = intercepts or tuple(0.0 for _ in coefficients)
    if len(offsets) != len(coefficients):
        raise ValueError("intercept dimensions do not match classes")
    logits = [sum(w * x for w, x in zip(row, scores)) + b for row, b in zip(coefficients, offsets)]
    pivot = max(logits)
    weights = [exp(value - pivot) for value in logits]
    total = sum(weights)
    return tuple(weight / total for weight in weights)


def l2_regularized_cross_entropy(probabilities: Sequence[float], target_index: int, coefficients: Sequence[Sequence[float]], regularization: float) -> float:
    if not 0 <= target_index < len(probabilities):
        raise ValueError("target index outside probability vector")
    if regularization < 0:
        raise ValueError("regularization cannot be negative")
    p = probabilities[target_index]
    if not 0.0 < p <= 1.0:
        raise ValueError("target probability must be in (0, 1]")
    penalty = regularization * sum(weight * weight for row in coefficients for weight in row)
    return -log(p) + penalty


def similarity_distance(z_current: Sequence[float], z_historical: Sequence[float], feature_weights: Sequence[float]) -> float:
    if not (len(z_current) == len(z_historical) == len(feature_weights)):
        raise ValueError("similarity dimensions do not match")
    return sqrt(sum(w * (a - b) ** 2 for a, b, w in zip(z_current, z_historical, feature_weights)))


def similarity_weight(distance: float, tau: float) -> float:
    if distance < 0 or tau <= 0:
        raise ValueError("distance/tau must be valid")
    return exp(-(distance * distance) / tau)


def beta_posterior(alpha: float, beta: float, successes: float, failures: float) -> tuple[float, float]:
    return alpha + successes, beta + failures


def decayed_beta(alpha: float, beta: float, successes: float, failures: float, rho: float) -> tuple[float, float]:
    if not 0 < rho <= 1:
        raise ValueError("rho must be in (0, 1]")
    return rho * alpha + successes, rho * beta + failures


@dataclass(frozen=True)
class ExecutionCost:
    spread: float = 0.0
    slippage: float = 0.0
    brokerage: float = 0.0
    exchange_charges: float = 0.0
    taxes: float = 0.0
    latency: float = 0.0
    market_impact: float = 0.0

    @property
    def total(self) -> float:
        return sum((self.spread, self.slippage, self.brokerage, self.exchange_charges, self.taxes, self.latency, self.market_impact))


def expected_net_value(expected_profit: float, expected_loss: float, execution_cost: ExecutionCost) -> float:
    return expected_profit - expected_loss - execution_cost.total


def risk_per_unit(entry_price: float, initial_stop: float) -> float:
    return entry_price - initial_stop


def gross_risk(risk_per_unit_value: float, quantity: float) -> float:
    return risk_per_unit_value * quantity


def position_size(max_risk: float, effective_risk_per_unit: float) -> int:
    if effective_risk_per_unit <= 0:
        raise ValueError("effective_risk_per_unit must be positive")
    return floor(max_risk / effective_risk_per_unit)


def enforce_lot_size(quantity: int, lot_size: int) -> int:
    if quantity < 0 or lot_size <= 0:
        raise ValueError("quantity and lot_size must be valid")
    return (quantity // lot_size) * lot_size


def continuation_value(expected_future_profit: float, expected_future_risk: float, expected_future_cost: float) -> float:
    return expected_future_profit - expected_future_risk - expected_future_cost


def profit_giveback(peak_profit: float, current_profit: float) -> float:
    return peak_profit - current_profit


def profit_floor(peak_price: float, allowed_giveback: float) -> float:
    return peak_price - allowed_giveback


def candidate_stop(original_risk_boundary: float, profit_floor_value: float, dynamic_risk_boundary: float) -> float:
    return max(original_risk_boundary, profit_floor_value, dynamic_risk_boundary)


def monotonic_stop(previous_stop: float, candidate_stop_value: float) -> float:
    return max(previous_stop, candidate_stop_value)


def maximum_accepted_risk(previous_risk: float, proposed_risk: float) -> float:
    return min(previous_risk, proposed_risk)


def conservative_expected_value(lower_confidence_bound: float) -> float:
    return lower_confidence_bound


def expected_value_per_risk(conservative_ev: float, effective_risk: float) -> float:
    if effective_risk <= 0:
        raise ValueError("effective risk must be positive")
    return conservative_ev / effective_risk


def target_stop_ev(target_probability: float, expected_gain: float, stop_probability: float, expected_loss: float, costs: float) -> float:
    return target_probability * expected_gain - stop_probability * expected_loss - costs
