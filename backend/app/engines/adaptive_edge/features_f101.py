"""A206 F-101 primitive features. Not an F-101 unlock. No DeltaVelocity."""
from __future__ import annotations

import math
from typing import Sequence

from .event_boundary import CanonicalMarketEvent
from .feature_engine import FeatureInput, FeatureProvenance, FeatureStatus
from .liquidity_imbalance import liquidity_imbalance_at

F101_FEATURE_NAMES: tuple[str, ...] = (
    "LogReturn",
    "LiquidityImbalance",
    "VolatilityRatio",
)
EPSILON = 1e-6


def log_return(price_t: float, price_prev: float) -> tuple[float | None, FeatureStatus]:
    if price_t <= 0 or price_prev <= 0:
        return None, FeatureStatus.MISSING
    return math.log(price_t / price_prev), FeatureStatus.VALID


def _sigma(returns: Sequence[float]) -> float:
    n = len(returns)
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / n
    return math.sqrt(var)


def volatility_ratio(
    returns_ending_at_t: Sequence[float],
    *,
    w_short: int,
    w_long: int,
    epsilon: float = EPSILON,
) -> tuple[float | None, FeatureStatus]:
    if w_short < 2 or w_short >= w_long:
        raise ValueError("A203: require W_short >= 2 and W_short < W_long")
    if len(returns_ending_at_t) < w_long:
        return None, FeatureStatus.MISSING
    window = list(returns_ending_at_t[-w_long:])
    short = window[-w_short:]
    sig_l = _sigma(window)
    sig_s = _sigma(short)
    return sig_s / max(sig_l, epsilon), FeatureStatus.VALID


def log_return_at(
    bar_events: Sequence[CanonicalMarketEvent],
    index: int,
) -> FeatureInput:
    if index < 1 or index >= len(bar_events):
        return FeatureInput(
            name="LogReturn",
            value=None,
            available_at=bar_events[index].available_at if bar_events else "",
            status=FeatureStatus.MISSING,
        )
    prev, cur = bar_events[index - 1], bar_events[index]
    value, status = log_return(float(cur.payload["close"]), float(prev.payload["close"]))
    return FeatureInput(
        name="LogReturn",
        value=value,
        available_at=cur.available_at,
        status=status,
        provenance=FeatureProvenance(source_event_ids=(prev.record_id, cur.record_id)),
    )


def volatility_ratio_at(
    returns: Sequence[float],
    available_at: str,
    source_ids: tuple[str, ...],
    *,
    w_short: int,
    w_long: int,
) -> FeatureInput:
    value, status = volatility_ratio(returns, w_short=w_short, w_long=w_long)
    return FeatureInput(
        name="VolatilityRatio",
        value=value,
        available_at=available_at,
        status=status,
        provenance=FeatureProvenance(source_event_ids=source_ids),
    )


def assemble_f101_inputs(
    *,
    bar_events: Sequence[CanonicalMarketEvent],
    index: int,
    tick_events: Sequence[CanonicalMarketEvent],
    w_short: int,
    w_long: int,
) -> tuple[FeatureInput, FeatureInput, FeatureInput]:
    """Build the A206 3-vector at bar close index. DeltaVelocity is not included."""
    lr = log_return_at(bar_events, index)
    returns: list[float] = []
    ids: list[str] = []
    for i in range(1, index + 1):
        item = log_return_at(bar_events, i)
        if item.status is FeatureStatus.VALID and item.value is not None:
            returns.append(item.value)
            ids.extend(item.provenance.source_event_ids)
    bar = bar_events[index]
    vr = volatility_ratio_at(
        returns,
        bar.available_at,
        tuple(ids[-w_long * 2 :]) if ids else (bar.record_id,),
        w_short=w_short,
        w_long=w_long,
    )
    li = liquidity_imbalance_at(tick_events, bar.available_at)
    return lr, li, vr
