"""Fail-closed handoff from Adaptive Edge decisions to execution adapters.

This module owns no broker semantics and creates no order parameters. It only
ensures that the final strategy execution gate is satisfied before an already-
constructed order intent is handed to an external dispatcher.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from .execution_gate import (
    REQUIRED_STRATEGY_FORMULAS,
    ExecutionBlockedError,
    ExecutionGateDecision,
    evaluate_strategy_promotion_gate,
    require_execution_authorized,
)


@dataclass(frozen=True)
class OrderIntent:
    """Provider-neutral order intent supplied by an already-authorized layer."""

    intent_id: str
    instrument_id: str
    side: str
    quantity: int


class OrderDispatcher(Protocol):
    def dispatch(self, intent: OrderIntent) -> object: ...


def dispatch_order(
    intent: OrderIntent,
    dispatcher: OrderDispatcher,
    *,
    formula_ids: Iterable[str] | None = None,
) -> object:
    """Gate and dispatch an existing intent; never synthesize an order.

    Two gates, both mandatory. The strategy must be promoted, and every required
    strategy formula must be resolved.

    `formula_ids` may only widen the formula scope, never narrow it. It
    previously replaced it, so a caller could authorize a dispatch by naming a
    single already-implemented formula and skip the fourteen that actually
    govern whether this strategy may trade.
    """
    promotion = evaluate_strategy_promotion_gate()
    if not promotion.authorized:
        raise ExecutionBlockedError(promotion)

    scope = REQUIRED_STRATEGY_FORMULAS
    if formula_ids is not None:
        extra = tuple(f for f in formula_ids if f not in scope)
        scope = scope + extra

    decision: ExecutionGateDecision = require_execution_authorized(scope)
    if not decision.authorized:
        raise RuntimeError("execution dispatch requires an authorized gate")
    return dispatcher.dispatch(intent)
