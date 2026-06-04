"""
Orchestrator — owns the EventBus and the lifecycle of registered agents.

Responsibilities: start/stop agents in order, run a heartbeat loop, and provide
graceful, idempotent shutdown + recovery hooks. Additive: constructing an
Orchestrator does nothing until start() is called, and the live app does not
start one unless explicitly wired.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, List, Optional

from app.bus.event_bus import EventBus
from app.domain.events import Heartbeat

log = logging.getLogger(__name__)


async def _maybe_await(value: Any) -> None:
    if inspect.isawaitable(value):
        await value


class Orchestrator:
    def __init__(self, bus: Optional[EventBus] = None, heartbeat_interval: float = 30.0) -> None:
        self.bus = bus or EventBus()
        self.heartbeat_interval = heartbeat_interval
        self._agents: List[Any] = []
        self._tasks: List[asyncio.Task] = []
        self.is_running = False

    def register(self, agent: Any) -> None:
        """Register an agent. Agents may expose async/sync start() and stop()."""
        self._agents.append(agent)

    async def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        for agent in self._agents:
            if hasattr(agent, "start"):
                await _maybe_await(agent.start())
        self._tasks.append(asyncio.create_task(self._heartbeat_loop()))
        log.info("Orchestrator started with %d agent(s)", len(self._agents))

    async def stop(self) -> None:
        self.is_running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        for agent in reversed(self._agents):
            if hasattr(agent, "stop"):
                try:
                    await _maybe_await(agent.stop())
                except Exception as exc:  # shutdown must not raise
                    log.warning("agent stop() failed: %s", exc)

    async def beat_once(self) -> None:
        await self.bus.publish(Heartbeat())

    async def _heartbeat_loop(self) -> None:
        try:
            while self.is_running:
                await self.beat_once()
                await asyncio.sleep(self.heartbeat_interval)
        except asyncio.CancelledError:
            pass
