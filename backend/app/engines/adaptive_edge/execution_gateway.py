from __future__ import annotations

from hashlib import sha256
from typing import Iterable

from .broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from .execution_adapter import CanonicalExecutionEvent, CanonicalOrderIntent, ExecutionAdapter
from .execution_event_registry import ExecutionEventRegistry
from .execution_gate import require_execution_authorized


class ExecutionGateway:
    """Compose governed submission, broker mapping and event registration.

    Explicit research/simulation execution requires a verifiable F-110
    admission proof in addition to the normal formula authorization gate.
    Production remains governed by the full registry.
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

    def submit(
        self,
        intent: CanonicalOrderIntent,
        *,
        f110_admission_token: str | None = None,
        formula_ids: tuple[str, ...] | None = None,
    ) -> str:
        """Submit a governed intent.

        Three authorization paths, in descending strength:

        * A gateway constructed with ``authorized_formula_ids`` is an explicit
          research/simulation gateway and demands a verifiable F-110 admission
          proof bound to this intent's fingerprint. A caller cannot downgrade
          that by passing ``formula_ids``.
        * Otherwise an explicit ``formula_ids`` scope is authorized against the
          registry, which is how the simulation pipeline runs its own formula set.
        * Otherwise the full production registry applies, which stays fail-closed
          while any strategy formula is LOCKED.
        """
        if self._authorized_formula_ids is not None:
            if not f110_admission_token:
                raise PermissionError("F-110 admission token required for research/simulation execution")
            expected = sha256(f"F-110|{intent.fingerprint()}".encode("utf-8")).hexdigest()
            if expected != f110_admission_token:
                raise PermissionError("invalid F-110 admission token")
            require_execution_authorized(self._authorized_formula_ids)
        elif formula_ids is not None:
            require_execution_authorized(formula_ids)
        else:
            require_execution_authorized()
        return self._adapter.submit(intent)

    def receive(self, broker_event: BrokerExecutionEvent) -> CanonicalExecutionEvent:
        canonical = self._mapper.map(broker_event)
        canonical.validate()
        self._event_registry.record(canonical)
        return canonical
