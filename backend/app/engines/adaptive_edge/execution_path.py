"""Governed composition of order intent, gateway, execution event, position and protection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .e2e import PositionState
from .execution_adapter import CanonicalExecutionEvent, CanonicalOrderIntent
from .execution_gateway import ExecutionGateway
from .order_intent_factory import OrderIntentFactory, OrderIntentInputs
from .position_projector import DeterministicPositionProjector
from .protection import ProtectionDecision, ProtectionEngine, ProtectionPolicy


@dataclass(frozen=True)
class ExecutionPathResult:
    intent: CanonicalOrderIntent
    broker_reference: str
    execution_event: CanonicalExecutionEvent
    position: PositionState
    protection: ProtectionDecision | None


class GovernedExecutionPath:
    """Compose existing execution boundaries without bypassing the gate."""

    def __init__(self, gateway: ExecutionGateway, projector: DeterministicPositionProjector, *, protection_policy: ProtectionPolicy | None = None) -> None:
        self._gateway = gateway
        self._projector = projector
        self._policy = protection_policy
        self._protection: ProtectionEngine | None = None

    def submit_and_project(self, *, selection_id: str, instrument_id: str, side: str, quantity: int, intent_version: str, created_at: str, broker_event_factory: Callable[[CanonicalOrderIntent, str], object], entry_price: float | None = None, mark: float | None = None) -> ExecutionPathResult:
        intent = OrderIntentFactory.create(OrderIntentInputs(selection_id, instrument_id, side, quantity, intent_version, created_at))
        broker_reference = self._gateway.submit(intent)
        event = self._gateway.receive(broker_event_factory(intent, broker_reference))
        position = self._projector.project(event)
        protection = None
        if self._policy is not None and entry_price is not None and mark is not None:
            if self._protection is None:
                self._protection = ProtectionEngine(self._policy, side=side, entry_price=entry_price)
            protection = self._protection.update(mark)
        return ExecutionPathResult(intent, broker_reference, event, position, protection)
