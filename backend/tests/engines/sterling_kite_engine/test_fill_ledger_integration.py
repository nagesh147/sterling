"""The ledger wired into the real execution paths: a journal entry, a broker
exit, and the daily-loss breaker that reads what they booked.

Broker protocol fixtures test safety; these are not market-performance data.
"""
from unittest.mock import AsyncMock
import pytest

from app.services.kite_engine import execution_lifecycle as life
from app.services.kite_engine import fill_ledger as ledger
from app.services.kite_engine import (monitor, order_journal as journal, positions,
                                      protective_stop, state)


class Client:
    _is_paper = False
    _account_id = "account"


@pytest.fixture
def entered(monkeypatch):
    """One live entry, 100 @ 121, confirmed through the journal and the ledger."""
    life._locks.clear()
    monkeypatch.setattr(protective_stop, "place_stop", AsyncMock(return_value=42))
    monkeypatch.setattr(protective_stop, "move_stop", AsyncMock(return_value=True))
    intent = journal.reserve(uid="u", account_id="account", strategy_id="sterling-kite",
        generation_id="v1", signal_id="signal", exchange="NFO", symbol="OPT", side="BUY",
        quantity=100, capital_required=12000, available_capital=100000,
        payload=dict(lot_size=50, entry_premium=120, stop_premium=100, stop_mode="both"))
    assert journal.claim_submission(intent.intent_key)
    return intent, Client()


def order(**over):
    base = dict(order_id="O1", tradingsymbol="OPT", exchange="NFO", product="NRML",
                quantity=100, transaction_type="BUY", status="COMPLETE",
                filled_quantity=100, average_price=121)
    base.update(over)
    return base


async def exit_event(uid, oid, *, filled, price, status="COMPLETE", client=None,
                     exchange_timestamp=None):
    event = dict(tradingsymbol="OPT", order_id=oid, transaction_type="SELL",
                 status=status, filled_quantity=filled, average_price=price)
    if exchange_timestamp:
        event["exchange_timestamp"] = exchange_timestamp
    await monitor.on_order_update(uid, event, client=client)


def holding():
    return ledger.inventory("account", "u", "OPT")


@pytest.mark.asyncio
async def test_a_confirmed_entry_lands_in_the_signed_ledger(entered):
    intent, client = entered
    assert await life.consume_order(client, "u", order(tag=intent.tag))
    assert holding().net_quantity == 100
    assert holding().average_cost == pytest.approx(121.0)
    assert holding().realized_pnl == 0.0


@pytest.mark.asyncio
async def test_replaying_the_same_entry_evidence_books_it_once(entered):
    intent, client = entered
    for _ in range(3):
        await life.consume_order(client, "u", order(tag=intent.tag))
    assert holding().net_quantity == 100
    assert len(ledger.increments("u")) == 1


@pytest.mark.asyncio
async def test_a_partial_entry_books_only_the_confirmed_quantity(entered):
    intent, client = entered
    await life.consume_order(client, "u", order(tag=intent.tag, status="OPEN",
                                                filled_quantity=40, average_price=120))
    assert holding().net_quantity == 40 and holding().average_cost == pytest.approx(120.0)
    await life.consume_order(client, "u", order(tag=intent.tag, status="CANCELLED",
                                                filled_quantity=40, average_price=120))
    assert holding().net_quantity == 40


@pytest.mark.asyncio
async def test_a_broker_exit_settles_in_the_ledger_and_reaches_the_breaker(entered):
    intent, client = entered
    await life.consume_order(client, "u", order(tag=intent.tag))
    p = positions.get("u", "OPT")
    p.exit_order_id = "X1"
    await exit_event("u", "X1", filled=100, price=101.0)
    assert positions.get("u", "OPT").status == positions.CLOSED
    assert holding().net_quantity == 0
    assert holding().realized_pnl == pytest.approx(-2000.0)
    # The INR daily-loss breaker reads this figure; it must see the real loss.
    assert state.daily_realized_pnl("u") == pytest.approx(-2000.0)
    assert state.daily_realized_pnl_strict("u") == pytest.approx(-2000.0)


@pytest.mark.asyncio
async def test_a_partial_exit_books_its_pnl_instead_of_flagging_it(entered):
    intent, client = entered
    await life.consume_order(client, "u", order(tag=intent.tag))
    p = positions.get("u", "OPT")
    p.exit_order_id = "X1"
    await exit_event("u", "X1", filled=40, price=131.0, status="OPEN")
    live = positions.get("u", "OPT")
    assert live.qty == 60 and live.status in (positions.OPEN, positions.PENDING)
    assert not live.pnl_reconciliation_required
    assert holding().net_quantity == 60
    assert holding().realized_pnl == pytest.approx(40 * 10.0)
    assert state.daily_realized_pnl("u") == pytest.approx(400.0)


@pytest.mark.asyncio
async def test_a_duplicate_exit_postback_does_not_book_the_pnl_twice(entered):
    intent, client = entered
    await life.consume_order(client, "u", order(tag=intent.tag))
    positions.get("u", "OPT").exit_order_id = "X1"
    await exit_event("u", "X1", filled=100, price=101.0)
    await exit_event("u", "X1", filled=100, price=101.0)
    assert holding().realized_pnl == pytest.approx(-2000.0)
    assert state.daily_realized_pnl("u") == pytest.approx(-2000.0)


@pytest.mark.asyncio
async def test_an_entry_the_ledger_never_saw_keeps_the_registry_accumulator(entered):
    """A position from before the ledger has no cost basis in it. Booking its exit
    there would open a phantom short, so that exit stays on the legacy path."""
    intent, client = entered
    p = life.register_pending(intent, "O1")
    positions.mark_filled("u", "OPT", 121.0, filled_qty=100, order_id="O1")
    p = positions.get("u", "OPT")
    p.exit_order_id = "X1"
    await exit_event("u", "X1", filled=100, price=101.0)
    assert holding() is None
    assert ledger.realized_pnl("u") == 0.0
    assert state.daily_realized_pnl("u") == pytest.approx(-2000.0)


@pytest.mark.asyncio
async def test_contradictory_exit_evidence_is_quarantined_not_booked(entered):
    intent, client = entered
    await life.consume_order(client, "u", order(tag=intent.tag))
    positions.get("u", "OPT").exit_order_id = "X1"
    await exit_event("u", "X1", filled=40, price=131.0, status="OPEN")
    # The broker restates the same 40 at a different price.
    ledger.record(account_id="account", uid="u", symbol="OPT", exchange="NFO",
                  side="SELL", order_id="X1", cumulative_quantity=40,
                  cumulative_value=40 * 999.0, source="exit")
    assert holding().reconciliation_required
    assert holding().realized_pnl == pytest.approx(400.0)  # the restatement was refused
    assert [c["reason"] for c in ledger.conflicts("u")] == ["cumulative_value_correction"]


@pytest.mark.asyncio
async def test_quarantined_ledger_evidence_blocks_automatic_entries(entered):
    from app.services.kite_engine import service
    intent, client = entered
    await life.consume_order(client, "u", order(tag=intent.tag))
    assert not [r for r in service.autoexec_preflight("u")
                if "Execution ledger" in r]
    ledger.record(account_id="account", uid="u", symbol="OPT", exchange="NFO",
                  side="BUY", order_id="O1", cumulative_quantity=100,
                  cumulative_value=100 * 999.0, source="entry")
    assert [r for r in service.autoexec_preflight("u")
            if r.startswith("Execution ledger reconciliation required")]


@pytest.mark.asyncio
async def test_the_ledger_records_the_lot_size_the_fill_was_booked_against(entered):
    intent, client = entered
    await life.consume_order(client, "u", order(tag=intent.tag))
    assert holding().lot_size == 50 and holding().net_lots == 2
    positions.get("u", "OPT").exit_order_id = "X1"
    await exit_event("u", "X1", filled=50, price=131.0, status="OPEN")
    assert holding().net_quantity == 50 and holding().net_lots == 1


@pytest.mark.asyncio
async def test_the_exchange_timestamp_reaches_the_ledger(entered):
    """Replay orders by exchange time, so an event with no real timestamp must
    record 0 rather than an arrival time dressed up as ordering information."""
    intent, client = entered
    await life.consume_order(client, "u", order(tag=intent.tag))
    positions.get("u", "OPT").exit_order_id = "X1"
    await exit_event("u", "X1", filled=100, price=101.0,
                     exchange_timestamp="2026-09-04 14:32:11")
    rows = {r["order_id"]: r for r in ledger.increments("u")}
    assert rows["X1"]["exchange_ts_ms"] == 1_788_512_531_000  # 2026-09-04 14:32:11 IST
    assert rows["O1"]["exchange_ts_ms"] == 0


@pytest.mark.asyncio
async def test_an_unreadable_ledger_books_nowhere_and_blocks(entered, monkeypatch):
    """The dangerous case: the ledger settled part of this exit, then went dark.
    Falling back to the legacy accumulator would book the whole position again."""
    intent, client = entered
    await life.consume_order(client, "u", order(tag=intent.tag))
    positions.get("u", "OPT").exit_order_id = "X1"
    monkeypatch.setattr(ledger, "inventory",
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("disk gone")))
    await exit_event("u", "X1", filled=100, price=101.0)
    monkeypatch.undo()
    assert state.daily_realized_pnl("u") == 0.0        # nothing invented
    assert positions.get("u", "OPT").pnl_reconciliation_required
    assert [r for r in __import__(
        "app.services.kite_engine.service", fromlist=["x"]).autoexec_preflight("u")
        if r.startswith("Fill-level PnL reconciliation required")]


@pytest.mark.asyncio
async def test_an_exit_the_ledger_already_holds_is_not_booked_again(entered):
    """The registry can lose its per-order exit tally (a restart, a replaced row)
    while the ledger keeps the fill. The legacy accumulator must stay out."""
    intent, client = entered
    await life.consume_order(client, "u", order(tag=intent.tag))
    ledger.record(account_id="account", uid="u", symbol="OPT", exchange="NFO",
                  side="SELL", order_id="X1", cumulative_quantity=100,
                  cumulative_value=100 * 101.0, source="exit")
    p = positions.get("u", "OPT")
    p.exit_order_id, p.exit_fills = "X1", {}
    await exit_event("u", "X1", filled=100, price=101.0)
    assert positions.get("u", "OPT").status == positions.CLOSED
    assert state.daily_realized_pnl("u") == pytest.approx(-2000.0)   # once, not twice


@pytest.mark.asyncio
async def test_broker_charges_are_applied_to_a_settled_exit(entered):
    intent, client = entered
    client.order_charges = AsyncMock(return_value=[{"charges": {"total": 21.5}}])
    await life.consume_order(client, "u", order(tag=intent.tag))
    # The entry is terminal, so its own charges are already in.
    assert holding().fees == pytest.approx(21.5) and not holding().realized_is_gross
    positions.get("u", "OPT").exit_order_id = "X1"
    await exit_event("u", "X1", filled=100, price=101.0, client=client)
    assert not holding().realized_is_gross
    assert holding().fees == pytest.approx(43.0)       # entry order and exit order
    assert holding().realized_pnl == pytest.approx(-2043.0)
    assert state.daily_realized_pnl("u") == pytest.approx(-2043.0)


@pytest.mark.asyncio
async def test_a_charges_failure_leaves_the_exit_booked_and_gross(entered):
    intent, client = entered
    client.order_charges = AsyncMock(side_effect=RuntimeError("rate limited"))
    await life.consume_order(client, "u", order(tag=intent.tag))
    positions.get("u", "OPT").exit_order_id = "X1"
    await exit_event("u", "X1", filled=100, price=101.0, client=client)
    assert holding().realized_pnl == pytest.approx(-2000.0)
    assert holding().realized_is_gross
