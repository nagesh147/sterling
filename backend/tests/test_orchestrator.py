"""
ORCHESTRATOR (Phase 3b) — lifecycle manager: start/stop agents, heartbeat.

Additive: the orchestrator is constructed and driven only by tests / opt-in
wiring; the live app startup is unchanged.
"""
import asyncio

import pytest

from app.bus.event_bus import EventBus
from app.agents.orchestrator import Orchestrator
from app.domain.events import Heartbeat


class _FakeAgent:
    def __init__(self):
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


@pytest.mark.asyncio
async def test_register_and_lifecycle_calls_agent_start_stop():
    orch = Orchestrator(bus=EventBus(), heartbeat_interval=0.01)
    agent = _FakeAgent()
    orch.register(agent)
    await orch.start()
    assert agent.started is True
    assert orch.is_running is True
    await orch.stop()
    assert agent.stopped is True
    assert orch.is_running is False


@pytest.mark.asyncio
async def test_beat_once_publishes_heartbeat():
    bus = EventBus()
    beats = []
    bus.subscribe(Heartbeat, lambda e: beats.append(e.event_type))
    orch = Orchestrator(bus=bus)
    await orch.beat_once()
    assert beats == ["Heartbeat"]


@pytest.mark.asyncio
async def test_heartbeat_loop_emits_while_running():
    bus = EventBus()
    beats = []
    bus.subscribe(Heartbeat, lambda e: beats.append(1))
    orch = Orchestrator(bus=bus, heartbeat_interval=0.01)
    await orch.start()
    await asyncio.sleep(0.05)
    await orch.stop()
    assert len(beats) >= 1


@pytest.mark.asyncio
async def test_stop_is_idempotent_and_safe_without_start():
    orch = Orchestrator(bus=EventBus())
    await orch.stop()  # never started — must not raise
    assert orch.is_running is False
