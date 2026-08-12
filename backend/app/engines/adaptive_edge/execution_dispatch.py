"""Fail-closed handoff from Adaptive Edge decisions to execution adapters.

This module owns no broker semantics and creates no order parameters. It only
ensures that the final strategy execution gate is satisfied before an already-
constructed order intent is handed to an external dispatcher.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from .execution_gate import ExecutionGateDecision, require_execution_authorized


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
    """Gate and dispatch an existing intent; never synthesize an order."""
    required = None if formula_ids is None else tuple(formula_ids)
    if required is None:
        decision: ExecutionGateDecision = require_execution_authorized()
    else:
        decision = require_execution_authorized(required)
    if not decision.authorized:
        raise RuntimeError("execution dispatch requires an authorized gate")
    return dispatcher.dispatch(intent)
