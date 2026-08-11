"""Canonical, provider-neutral Adaptive Edge feature state.

Providers map their validated canonical events into this contract. Strategy
mathematics consumes only this normalized state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite


@dataclass(frozen=True)
class MarketSnapshot:
    instrument: str
    timestamp: datetime
    bid: float
    ask: float
    ltp: float
    ttq: float
    bid_qty: float
    ask_qty: float
    trade_price: float | None = None
    trade_volume: float = 0.0


@dataclass(frozen=True)
class FeatureState:
    instrument: str
    decision_time: datetime
    mid: float
    spread: float
    relative_spread: float
    price_change: float
    return_value: float | None
    velocity: float | None
    acceleration: float | None
    incremental_volume: float | None
    aggressive_buy_volume: float
    aggressive_sell_volume: float
    unknown_volume: float
    delta: float
    cumulative_delta: float
    delta_velocity: float | None
    delta_acceleration: float | None
    liquidity_imbalance: float | None
    data_ok: bool


def _base_data_ok(snapshot: MarketSnapshot) -> bool:
    if not snapshot.instrument.strip():
        return False
    required = (
        snapshot.bid,
        snapshot.ask,
        snapshot.ltp,
        snapshot.ttq,
        snapshot.bid_qty,
        snapshot.ask_qty,
        snapshot.trade_volume,
    )
    if not all(isfinite(x) for x in required):
        return False
    if snapshot.bid <= 0 or snapshot.ask <= 0 or snapshot.ltp <= 0:
        return False
    if snapshot.ask < snapshot.bid:
        return False
    if snapshot.ttq < 0 or snapshot.bid_qty < 0 or snapshot.ask_qty < 0:
        return False
    if snapshot.trade_volume < 0:
        return False
    if snapshot.trade_price is not None and (
        not isfinite(snapshot.trade_price) or snapshot.trade_price <= 0
    ):
        return False
    return True


def build_feature_state(
    current: MarketSnapshot,
    previous: MarketSnapshot | None,
    previous_velocity: float | None = None,
    previous_delta: float | None = None,
    previous_delta_velocity: float | None = None,
    cumulative_delta: float = 0.0,
) -> FeatureState:
    data_ok = _base_data_ok(current)
    if previous is not None and current.instrument != previous.instrument:
        raise ValueError("snapshots must belong to the same instrument")

    mid = (current.bid + current.ask) / 2.0
    spread = current.ask - current.bid
    relative_spread = spread / mid if mid > 0 else 0.0

    if previous is None:
        return FeatureState(
            current.instrument,
            current.timestamp,
            mid,
            spread,
            relative_spread,
            0.0,
            None,
            None,
            None,
            None,
            0.0,
            0.0,
            0.0,
            0.0,
            cumulative_delta,
            None,
            None,
            (current.bid_qty - current.ask_qty) / (current.bid_qty + current.ask_qty)
            if current.bid_qty + current.ask_qty > 0
            else None,
            data_ok,
        )

    dt = (current.timestamp - previous.timestamp).total_seconds()
    if dt <= 0:
        raise ValueError("market snapshots must be strictly chronological")

    price_change = current.ltp - previous.ltp
    return_value = price_change / previous.ltp if previous.ltp > 0 else None
    velocity = price_change / dt
    acceleration = (
        (velocity - previous_velocity) / dt
        if previous_velocity is not None
        else None
    )

    incremental_volume = current.ttq - previous.ttq
    if incremental_volume < 0:
        incremental_volume = None
        data_ok = False

    buy = sell = unknown = 0.0
    if current.trade_price is not None and current.trade_volume > 0:
        if current.trade_price >= current.ask:
            buy = current.trade_volume
        elif current.trade_price <= current.bid:
            sell = current.trade_volume
        elif current.bid < current.trade_price < current.ask:
            unknown = current.trade_volume

    delta = buy - sell
    delta_velocity = (
        (delta - previous_delta) / dt if previous_delta is not None else None
    )
    delta_acceleration = (
        (delta_velocity - previous_delta_velocity) / dt
        if delta_velocity is not None and previous_delta_velocity is not None
        else None
    )
    cumulative_delta += delta

    denominator = current.bid_qty + current.ask_qty
    liquidity = (
        (current.bid_qty - current.ask_qty) / denominator
        if denominator > 0
        else None
    )

    return FeatureState(
        current.instrument,
        current.timestamp,
        mid,
        spread,
        relative_spread,
        price_change,
        return_value,
        velocity,
        acceleration,
        incremental_volume,
        buy,
        sell,
        unknown,
        delta,
        cumulative_delta,
        delta_velocity,
        delta_acceleration,
        liquidity,
        data_ok,
    )
