"""Composed Adaptive Edge execution path.

SelectedInstrument + F-108 sizing + authorization
    → CanonicalOrderIntent
    → ExecutionGateway (require_execution_authorized)
    → BrokerEvent
    → CanonicalExecutionEvent
    → PositionState

No strategy mathematics is invented here. Production remains BLOCKED unless
an explicit authorized formula set is supplied by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .admission import require_entry_admitted
from .broker_event_mapper import DEFAULT_BROKER_STATUS_MAP, BrokerEventMapper, BrokerExecutionEvent
from .e2e import PositionState, ReplayContext, SelectedInstrument
from .execution_adapter import (
    BrokerTransport,
    CanonicalExecutionEvent,
    CanonicalExecutionStatus,
    CanonicalOrderIntent,
    ExecutionAdapter,
)
from .execution_event_registry import ExecutionEventRegistry
from .execution_gateway import ExecutionGateway
from .order_intent import Authorization, CanonicalOrderIntentFactory, authorization_reference
from .position_projector import DeterministicPositionProjector
from .risk_sizing import PositionSizingAssessment


@dataclass(frozen=True)
class ExecutionStep:
    execution: CanonicalExecutionEvent
    position: PositionState


@dataclass(frozen=True)
class ExecutionPathResult:
    order: CanonicalOrderIntent
    broker_reference: str
    execution: CanonicalExecutionEvent
    position: PositionState


class AdaptiveEdgeExecutionPath:
    """Stateful composer for one simulation/research execution path."""

    def __init__(
        self,
        *,
        transport: BrokerTransport,
        formula_ids: tuple[str, ...] | None = None,
        status_map: Mapping[str, CanonicalExecutionStatus] | None = None,
    ) -> None:
        self._transport = transport
        self._gateway = ExecutionGateway(
            ExecutionAdapter(transport),
            BrokerEventMapper(status_map or DEFAULT_BROKER_STATUS_MAP),
            ExecutionEventRegistry(),
        )
        self._formula_ids = formula_ids
        self._projector: DeterministicPositionProjector | None = None
        self._order_side_map: dict[str, str] = {}

    def submit(self, intent: CanonicalOrderIntent) -> str:
        intent.validate()
        self._order_side_map.setdefault(intent.order_intent_id, intent.side)
        return self._gateway.submit(intent, self._formula_ids)

    def receive(self, broker_event: BrokerExecutionEvent) -> CanonicalExecutionEvent:
        return self._gateway.receive(broker_event)

    def receive_and_project(
        self,
        broker_event: BrokerExecutionEvent,
        *,
        instrument_id: str,
        side: str,
        risk_boundary: float | None = None,
        order_side_map: Mapping[str, str] | None = None,
        position_id: str | None = None,
    ) -> ExecutionStep:
        if order_side_map:
            self._order_side_map.update(order_side_map)
        event = self.receive(broker_event)
        if self._projector is None:
            self._projector = DeterministicPositionProjector(
                position_id or f"POS-{instrument_id}",
                instrument_id,
                side=side,
                order_side_map=self._resolve_side,
                risk_boundary=risk_boundary,
            )
        elif risk_boundary is not None:
            self._projector.set_risk_boundary(risk_boundary)
        position = self._projector.project(event)
        return ExecutionStep(execution=event, position=position)

    def submit_and_project(
        self,
        *,
        instrument: SelectedInstrument,
        authorization: Authorization,
        sizing: PositionSizingAssessment,
        side: str,
        created_at: str,
        broker_event: BrokerExecutionEvent,
        replay_context: ReplayContext | None = None,
        risk_boundary: float | None = None,
        order_type: str = "MARKET",
        limit_price: float | None = None,
        causal_parent_ids: tuple[str, ...] = (),
        consumed_authorization_ids: frozenset[str] = frozenset(),
        entered_opportunity_ids: frozenset[str] = frozenset(),
    ) -> ExecutionPathResult:
        open_position = None
        if self._projector is not None and self._projector.current_quantity > 0:
            open_position = PositionState(
                position_id=self._projector.position_id,
                instrument_id=self._projector.instrument_id,
                quantity=self._projector.current_quantity,
                average_price=self._projector.average_price,
                lifecycle_state=self._projector.lifecycle_state,
                source_execution_event_id=self._projector.fills[-1].execution_event_id
                if self._projector.fills
                else "open",
            )
        require_entry_admitted(
            open_position=open_position,
            authorization_id=authorization_reference(authorization),
            opportunity_id=getattr(authorization, "opportunity_id", authorization_reference(authorization)),
            decision_time=created_at,
            consumed_authorization_ids=consumed_authorization_ids,
            entered_opportunity_ids=entered_opportunity_ids,
        )
        factory = CanonicalOrderIntentFactory(
            authorization=authorization,
            sizing=sizing,
            side=side,
            created_at=created_at,
            order_type=order_type,
            limit_price=limit_price,
            causal_parent_ids=causal_parent_ids,
            replay_context=replay_context,
        )
        intent = factory.create(instrument)
        broker_reference = self.submit(intent)
        bound = _bind_broker_event(intent, broker_event, broker_reference)
        step = self.receive_and_project(
            bound,
            instrument_id=instrument.instrument_id,
            side=side,
            risk_boundary=risk_boundary,
            position_id=f"POS-{intent.order_intent_id}",
        )
        return ExecutionPathResult(
            order=intent,
            broker_reference=broker_reference,
            execution=step.execution,
            position=step.position,
        )

    def _resolve_side(self, order_intent_id: str) -> str:
        if order_intent_id in self._order_side_map:
            return self._order_side_map[order_intent_id]
        if self._projector is None:
            return "BUY"
        return self._projector.initial_side


def _bind_broker_event(
    intent: CanonicalOrderIntent,
    event: BrokerExecutionEvent,
    broker_reference: str,
) -> BrokerExecutionEvent:
    rebound = event.order_intent_id in {"", "pending"} or event.order_intent_id != intent.order_intent_id
    event_id = event.broker_event_id
    if rebound and (event.order_intent_id in {"", "pending"} or event_id.endswith("pending")):
        event_id = f"BE-{intent.order_intent_id}"
    return BrokerExecutionEvent(
        broker_event_id=event_id,
        order_intent_id=intent.order_intent_id,
        broker_status=event.broker_status,
        event_time=event.event_time,
        broker_reference=event.broker_reference or broker_reference,
        filled_quantity=event.filled_quantity,
        fill_price=event.fill_price,
        receipt_time=event.receipt_time,
    )
