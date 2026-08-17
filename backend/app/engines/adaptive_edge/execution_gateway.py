from __future__ import annotations

from .broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from .execution_adapter import CanonicalExecutionEvent, CanonicalOrderIntent, ExecutionAdapter
from .execution_event_registry import ExecutionEventRegistry
from .execution_gate import require_execution_authorized


class ExecutionGateway:
    """Compose order submission, broker mapping, and event registration."""

    def __init__(self, adapter: ExecutionAdapter, mapper: BrokerEventMapper, event_registry: ExecutionEventRegistry) -> None:
        self._adapter = adapter
        self._mapper = mapper
        self._event_registry = event_registry

    def submit(self, intent: CanonicalOrderIntent, formula_ids: tuple[str, ...] | None = None) -> str:
        if formula_ids is None:
            require_execution_authorized()
        else:
            require_execution_authorized(formula_ids)
        return self._adapter.submit(intent)

    def receive(self, broker_event: BrokerExecutionEvent) -> CanonicalExecutionEvent:
        canonical = self._mapper.map(broker_event)
        canonical.validate()
        self._event_registry.record(canonical)
        return canonical
