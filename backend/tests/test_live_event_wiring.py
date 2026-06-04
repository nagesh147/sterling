"""
LIVE EVENT WIRING (Phase 3 go-live) — flag-gated event bus + agents.

Default OFF: event_emit is a no-op until configure() runs at startup (only when
enable_event_bus is set). Here we configure a bus + PNLAgent directly and prove
paper_store.close_position emits PositionClosed end-to-end. Existing paper/pnl
tests run close_position with the bus UNconfigured, proving the emit is inert by
default.
"""
import asyncio

import pytest

from app.bus.event_bus import EventBus
from app.agents import PNLAgent
from app.domain.events import FillReceived, PositionClosed
from app.services import event_emit
from app.services import paper_store
from app.schemas.execution import SizedTrade, TradeStructure
from app.schemas.directional import Direction


# ── bus.publish_sync ───────────────────────────────────────────────────────
def test_publish_sync_calls_sync_handler():
    bus = EventBus()
    seen = []
    bus.subscribe(PositionClosed, lambda e: seen.append(e.realized_pnl_usd))
    bus.publish_sync(PositionClosed(symbol="BTCUSD", realized_pnl_usd=42.0))
    assert seen == [42.0]


@pytest.mark.asyncio
async def test_publish_sync_schedules_async_handler():
    bus = EventBus()
    seen = []

    async def _h(e):
        seen.append(e.symbol)

    bus.subscribe(FillReceived, _h)
    bus.publish_sync(FillReceived(symbol="ETHUSD", side="buy", size=1, price=3000))
    await asyncio.sleep(0)  # let the scheduled task run
    assert seen == ["ETHUSD"]


# ── event_emit module ──────────────────────────────────────────────────────
def test_emit_is_noop_when_not_configured():
    event_emit.reset()
    assert event_emit.is_enabled() is False
    event_emit.emit_position_closed("BTCUSD", 10.0)   # must not raise
    event_emit.emit_fill("BTCUSD", "buy", 1, 50000)   # must not raise


def test_emit_reaches_pnl_agent_then_reset():
    bus = EventBus()
    pnl = PNLAgent(bus=bus)
    event_emit.configure(bus, {"pnl": pnl})
    try:
        assert event_emit.is_enabled() is True
        event_emit.emit_position_closed("BTCUSD", 125.0)
        event_emit.emit_fill("BTCUSD", "buy", 1, 50000)
        snap = pnl.snapshot()
        assert snap["realized_pnl_usd"] == 125.0
        assert snap["fills"] == 1
    finally:
        event_emit.reset()
    assert event_emit.is_enabled() is False


# ── end-to-end: close_position → PositionClosed → PNLAgent ─────────────────
def _futures_sized() -> SizedTrade:
    return SizedTrade(
        structure=TradeStructure(
            structure_type="futures", direction=Direction.LONG, legs=[],
            max_loss=200.0, max_gain=None, net_premium=0.0, risk_reward=2.0,
            score=80.0, score_breakdown={}, leverage=5, entry_price=100.0,
        ),
        contracts=1, position_value=200.0, max_risk_usd=200.0, capital_at_risk_pct=1.0,
    )


def test_close_position_emits_when_bus_configured():
    bus = EventBus()
    pnl = PNLAgent(bus=bus)
    event_emit.configure(bus, {"pnl": pnl})
    try:
        pos = paper_store.add_position("BTC", _futures_sized(), entry_spot_price=100.0)
        paper_store.close_position(pos.id, exit_spot_price=110.0)  # +10 move
        snap = pnl.snapshot()
        assert snap["realized_pnl_usd"] != 0.0   # close emitted a non-zero PnL
    finally:
        event_emit.reset()


def test_close_position_safe_when_not_configured():
    event_emit.reset()  # bus unconfigured
    pos = paper_store.add_position("BTC", _futures_sized(), entry_spot_price=100.0)
    closed = paper_store.close_position(pos.id, exit_spot_price=110.0)
    assert closed is not None and closed.status.value == "closed"
