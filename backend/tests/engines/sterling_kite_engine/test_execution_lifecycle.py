"""Broker protocol fixtures test safety; these are not market-performance data."""
from unittest.mock import AsyncMock
import pytest

from app.services.kite_engine import execution_lifecycle as life
from app.services.kite_engine import order_journal as journal, positions, monitor, protective_stop


class Client:
    _is_paper = False
    _account_id = "account"


@pytest.fixture
def setup(monkeypatch):
    life._locks.clear()
    place = AsyncMock(return_value=42)
    monkeypatch.setattr(protective_stop, "place_stop", place)
    monkeypatch.setattr(protective_stop, "move_stop", AsyncMock(return_value=True))
    intent = journal.reserve(uid="u", account_id="account", strategy_id="sterling-kite",
        generation_id="v1", signal_id="signal", exchange="NFO", symbol="OPT", side="BUY",
        quantity=100, capital_required=12000, available_capital=100000,
        payload=dict(lot_size=50, entry_premium=120, stop_premium=100, stop_mode="both"))
    assert journal.claim_submission(intent.intent_key)
    order = dict(order_id="O1", tag=intent.tag, tradingsymbol="OPT", exchange="NFO",
                 product="NRML", quantity=100, transaction_type="BUY", status="COMPLETE",
                 filled_quantity=100, average_price=121)
    return intent, order, Client(), place


@pytest.mark.asyncio
async def test_ack_registers_zero_quantity_and_no_stop(setup):
    intent, _, client, place = setup
    journal.transition(intent.intent_key, "SUBMITTED", order_id="O1")
    p = life.register_pending(intent, "O1")
    assert p.qty == 0 and p.entry_pending and p.entry_requested_qty == 100
    place.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_entry_recovers_without_registry_or_resubmission(setup):
    intent, order, client, place = setup
    journal.transition(intent.intent_key, "UNKNOWN")
    client.get_orders = AsyncMock(return_value=[order])
    await life.recover(client, "u")
    p = positions.get("u", "OPT")
    assert p.qty == 100 and p.fill_price == 121 and not p.entry_pending
    assert p.gtt_id == 42 and p.account_id == "account"
    assert place.await_args.kwargs["qty"] == 100
    assert journal.find(uid="u", account_id="account", order_id="O1").state == "FILLED"


@pytest.mark.asyncio
async def test_partial_open_and_cancel_protect_only_confirmed_quantity(setup):
    intent, order, client, place = setup
    await monitor.on_order_update("u", {**order, "status": "OPEN", "filled_quantity": 50}, client=client)
    p = positions.get("u", "OPT")
    assert p.qty == 50 and p.entry_pending
    assert place.await_args.kwargs["qty"] == 50
    await monitor.on_order_update("u", {**order, "status": "CANCELLED", "filled_quantity": 50}, client=client)
    assert p.qty == 50 and not p.entry_pending and p.status == positions.OPEN
    assert journal.find(uid="u", account_id="account", order_id="O1").state == "CANCELLED"


@pytest.mark.asyncio
async def test_duplicate_entry_event_does_not_restore_exited_quantity(setup):
    _, order, client, place = setup
    await life.consume_order(client, "u", order)
    p = positions.get("u", "OPT")
    p.qty = 50  # confirmed partial exit after the entry was already projected
    positions.persist_strict("u")
    await life.consume_order(client, "u", order)
    assert p.qty == 50 and place.await_count == 1


@pytest.mark.asyncio
async def test_committed_fill_recovers_after_projection_crash(setup, monkeypatch):
    intent, order, client, place = setup
    original = life.register_pending
    def crash(*args):
        raise RuntimeError("simulated process failure before registry projection")
    monkeypatch.setattr(life, "register_pending", crash)
    with pytest.raises(RuntimeError):
        await life.consume_order(client, "u", order)
    assert journal.pending_projection("u", "account")
    monkeypatch.setattr(life, "register_pending", original)
    client.get_orders = AsyncMock(return_value=[order])
    await life.recover(client, "u")
    assert positions.get("u", "OPT").qty == 100
    assert not journal.pending_projection("u", "account")


@pytest.mark.asyncio
async def test_unknown_gtt_outcome_is_not_retried(setup):
    _, order, client, place = setup
    place.return_value = None
    await life.consume_order(client, "u", order)
    await life.consume_order(client, "u", order)
    assert positions.get("u", "OPT").protection_pending
    assert place.await_count == 1


@pytest.mark.asyncio
async def test_wrong_venue_never_projects_or_arms(setup):
    intent, order, client, place = setup
    await life.consume_order(client, "u", {**order, "exchange": "BFO"})
    assert positions.get("u", "OPT") is None
    assert journal.unresolved("u")
    place.assert_not_awaited()
