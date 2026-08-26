"""Canonical LiquidityImbalance primitive (not F-101).

LI_t = (Q^B - Q^A) / (Q^B + Q^A) only when LQ_t > 0.
LQ_t = 0 is undefined in the exact-math spec and fails closed as MISSING.
This module does not unlock F-101.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from .event_boundary import CanonicalMarketEvent
from .feature_engine import FeatureInput, FeatureProvenance, FeatureStatus


def _parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return parsed


def compute_liquidity_imbalance(
    bidqty: float | None, askqty: float | None
) -> tuple[float | None, FeatureStatus]:
    if bidqty is None or askqty is None:
        return None, FeatureStatus.MISSING
    try:
        bid = float(bidqty)
        ask = float(askqty)
    except (TypeError, ValueError):
        return None, FeatureStatus.INVALID
    if bid < 0 or ask < 0:
        return None, FeatureStatus.MISSING
    depth = bid + ask
    if depth <= 0:
        return None, FeatureStatus.MISSING
    return (bid - ask) / depth, FeatureStatus.VALID


def last_quote_at_or_before(
    events: Sequence[CanonicalMarketEvent],
    decision_time: str,
) -> CanonicalMarketEvent | None:
    cutoff = _parse_ts(decision_time)
    eligible = [
        event
        for event in events
        if event.event_type == "tick" and _parse_ts(event.available_at) <= cutoff
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda event: (event.event_time, event.sequence or 0, event.record_id))


def liquidity_imbalance_at(
    events: Iterable[CanonicalMarketEvent],
    decision_time: str,
) -> FeatureInput:
    chosen = last_quote_at_or_before(tuple(events), decision_time)
    if chosen is None:
        return FeatureInput(
            name="LiquidityImbalance",
            value=None,
            available_at=decision_time,
            status=FeatureStatus.MISSING,
            provenance=FeatureProvenance(source_event_ids=()),
        )
    value, status = compute_liquidity_imbalance(
        chosen.payload.get("bidqty"),
        chosen.payload.get("askqty"),
    )
    return FeatureInput(
        name="LiquidityImbalance",
        value=value,
        available_at=chosen.available_at,
        status=status,
        provenance=FeatureProvenance(source_event_ids=(chosen.record_id,)),
    )
