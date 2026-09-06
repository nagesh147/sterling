"""
EVENT BUS (Phase 3a) — in-process async pub/sub + TradeEvent taxonomy.

Pure, additive infrastructure: nothing in the existing app subscribes yet.
Handler errors are isolated so one bad subscriber never blocks the publisher
or other subscribers.
"""
import pytest

from app.bus.event_bus import EventBus
from app.domain.events import (
    SignalRaised, OrderSubmitted, OrderRejected, FillReceived,
    PositionClosed, RiskBreach, Heartbeat,
)
from app.domain.models import TradeEvent


def test_event_types_carry_their_name_and_timestamp():
    ev = FillReceived(symbol="NIFTYUSD", side="buy", size=1.0, price=50000.0)
    assert ev.event_type == "FillReceived"
    assert ev.timestamp_ms > 0
    assert ev.symbol == "NIFTYUSD"
    assert isinstance(ev, TradeEvent)


@pytest.mark.asyncio
async def test_subscribe_and_publish_async_and_sync_handlers():
    bus = EventBus()
    seen = []
    bus.subscribe(FillReceived, lambda e: seen.append(("sync", e.symbol)))

    async def _async_handler(e):
        seen.append(("async", e.symbol))

    bus.subscribe(FillReceived, _async_handler)
    await bus.publish(FillReceived(symbol="BANKNIFTYUSD", side="sell", size=2.0, price=3000.0))
    assert ("sync", "BANKNIFTYUSD") in seen
    assert ("async", "BANKNIFTYUSD") in seen


@pytest.mark.asyncio
async def test_handler_only_receives_subscribed_type():
    bus = EventBus()
    got = []
    bus.subscribe(OrderSubmitted, lambda e: got.append(e.event_type))
    await bus.publish(OrderRejected(payload={"code": "x"}))
    assert got == []  # OrderRejected is not OrderSubmitted


@pytest.mark.asyncio
async def test_subscribe_to_base_TradeEvent_receives_all():
    bus = EventBus()
    all_events = []
    bus.subscribe(TradeEvent, lambda e: all_events.append(e.event_type))
    await bus.publish(SignalRaised(payload={"underlying": "NIFTY"}))
    await bus.publish(Heartbeat())
    assert all_events == ["SignalRaised", "Heartbeat"]


@pytest.mark.asyncio
async def test_failing_handler_is_isolated():
    bus = EventBus()
    delivered = []

    def _boom(e):
        raise RuntimeError("handler blew up")

    bus.subscribe(RiskBreach, _boom)
    bus.subscribe(RiskBreach, lambda e: delivered.append(e.event_type))
    # publish must not raise despite the failing handler
    await bus.publish(RiskBreach(payload={"rule": "max_dd"}))
    assert delivered == ["RiskBreach"]
    assert bus.last_errors and isinstance(bus.last_errors[0], RuntimeError)


@pytest.mark.asyncio
async def test_position_closed_carries_pnl():
    ev = PositionClosed(symbol="NIFTYUSD", realized_pnl_usd=125.5)
    assert ev.event_type == "PositionClosed"
    assert ev.realized_pnl_usd == 125.5
