"""StrategyAgent — runs an injected signal generator → Signals, on the bus."""
from __future__ import annotations

import inspect
from typing import Any, Callable, List, Optional

from app.bus.event_bus import EventBus
from app.domain.events import SignalRaised
from app.domain.models import Signal


class StrategyAgent:
    def __init__(self, generator: Callable[..., Any], bus: Optional[EventBus] = None) -> None:
        self.generator = generator
        self.bus = bus

    async def run(self, *args, **kwargs) -> List[Signal]:
        signals = self.generator(*args, **kwargs)
        if inspect.isawaitable(signals):
            signals = await signals
        if self.bus is not None:
            for s in signals:
                await self.bus.publish(SignalRaised(payload={
                    "underlying": s.underlying, "direction": s.direction,
                    "score": s.score, "source": s.source,
                }))
        return list(signals)
