"""
EventBus — minimal in-process async pub/sub over asyncio.

No external broker. Handlers may be sync or async. A handler raising never
blocks the publisher or other handlers (errors are isolated and recorded in
`last_errors`). Subscribing to a base type (e.g. TradeEvent) receives every
subclass — useful for audit/log sinks.

This is additive: nothing in the existing app subscribes until an Orchestrator
or agent wires it (Phase 3b/3c), so importing it changes no behavior.
"""
from __future__ import annotations

import inspect
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Type

from app.domain.models import TradeEvent

log = logging.getLogger(__name__)

Handler = Callable[[TradeEvent], Any]


class EventBus:
    def __init__(self) -> None:
        self._subs: Dict[Type[TradeEvent], List[Handler]] = defaultdict(list)
        self.last_errors: List[BaseException] = []

    def subscribe(self, event_type: Type[TradeEvent], handler: Handler) -> None:
        """Register `handler` for `event_type` and all of its subclasses."""
        self._subs[event_type].append(handler)

    def unsubscribe(self, event_type: Type[TradeEvent], handler: Handler) -> None:
        if handler in self._subs.get(event_type, []):
            self._subs[event_type].remove(handler)

    async def publish(self, event: TradeEvent) -> None:
        """Deliver `event` to every handler whose subscribed type it is an
        instance of. Awaits async handlers; isolates handler exceptions."""
        self.last_errors = []
        for etype, handlers in list(self._subs.items()):
            if isinstance(event, etype):
                for handler in list(handlers):
                    try:
                        result = handler(event)
                        if inspect.isawaitable(result):
                            await result
                    except Exception as exc:  # never let one handler break others
                        self.last_errors.append(exc)
                        log.warning(
                            "EventBus handler error for %s: %s", event.event_type, exc
                        )

    def clear(self) -> None:
        self._subs.clear()
        self.last_errors = []
