"""F-007 / F-008 executable references from the last causal quote.

BUY reference = executable ASK. SELL reference = executable BID.
Not an F-101 unlock. Missing quotes fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .event_boundary import CanonicalMarketEvent
from .feature_engine import FeatureStatus
from .liquidity_imbalance import last_quote_at_or_before


@dataclass(frozen=True)
class ExecutableReference:
    side: str
    price: float | None
    available_at: str
    status: FeatureStatus
    formula_id: str
    source_event_id: str | None


def executable_reference(
    ticks: Sequence[CanonicalMarketEvent],
    decision_time: str,
    side: str,
) -> ExecutableReference:
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    quote = last_quote_at_or_before(ticks, decision_time)
    formula_id = "F-007" if side == "BUY" else "F-008"
    field = "ask" if side == "BUY" else "bid"
    if quote is None:
        return ExecutableReference(
            side=side,
            price=None,
            available_at=decision_time,
            status=FeatureStatus.MISSING,
            formula_id=formula_id,
            source_event_id=None,
        )
    raw = quote.payload.get(field)
    try:
        price = float(raw) if raw is not None and raw != "" else None
    except (TypeError, ValueError):
        price = None
    if price is None or price <= 0:
        return ExecutableReference(
            side=side,
            price=None,
            available_at=quote.available_at,
            status=FeatureStatus.MISSING,
            formula_id=formula_id,
            source_event_id=quote.record_id,
        )
    return ExecutableReference(
        side=side,
        price=price,
        available_at=quote.available_at,
        status=FeatureStatus.VALID,
        formula_id=formula_id,
        source_event_id=quote.record_id,
    )
