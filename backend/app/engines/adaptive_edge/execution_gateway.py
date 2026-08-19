from __future__ import annotations

from typing import Iterable

from .broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from .execution_adapter import CanonicalExecutionEvent, CanonicalOrderIntent, ExecutionAdapter
from .execution_event_registry import ExecutionEventRegistry
from .execution_gate import require_execution_authorized


class ExecutionGateway:
    """Compose submission, broker mapping and event registration.

    No formula scope means the production gate is evaluated in full. An explicit
    formula scope is allowed only for research/simulation callers and is still
    evaluated by the same fail-closed registry.
    """

    def __init__(
        self,
        adapter: ExecutionAdapter,
        mapper: BrokerEventMapper,
        event_registry: ExecutionEventRegistry,
        *,
        authorized_formula_ids: Iterable[str] | None = None,
    ) -> None:
        self._adapter = adapter
        self._mapper = mapper
        self._event_registry = event_registry
        self._authorized_formula_ids = None if authorized_formula_ids is None else tuple(authorized_formula_ids)

    @property
    def authorized_formula_ids(self) -> tuple[str, ...] | None:
        return self._authorized_formula_ids

    def submit(self, intent: CanonicalOrderIntent) -> str:
        require_execution_authorized(self._authorized_formula_ids) if self._authorized_formula_ids is not None else require_execution_authorized()
        return self._adapter.submit(intent)

    def receive(self, broker_event: BrokerExecutionEvent) -> CanonicalExecutionEvent:
        canonical = self._mapper.map(broker_event)
        canonical.validate()
        self._event_registry.record(canonical)
        return canonical
