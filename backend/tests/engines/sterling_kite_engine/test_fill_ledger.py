"""The signed execution ledger: inventory, cost and realized PnL under the
things a real broker feed actually does — partial fills, partial cancels,
several exits, restatements, duplicate and reordered postbacks, and a crash.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services import db
from app.services.kite_engine import fill_ledger as ledger


@pytest.fixture(autouse=True)
def isolated_ledger():
    prior = db._available
    db.init()
    ledger.clear_for_tests('u')
    yield
    ledger.clear_for_tests('u')
    db._available = prior


SYMBOL = 'NIFTY26SEP25000CE'


def fill(order_id, qty, value, side='BUY', *, symbol=SYMBOL, source='entry',
         fees=0.0, ts=0, uid='u'):
    return ledger.record(account_id='a', uid=uid, symbol=symbol, exchange='NFO',
                         side=side, order_id=order_id, cumulative_quantity=qty,
                         cumulative_value=value, source=source, fees=fees,
                         fees_source='broker' if fees else '', exchange_ts_ms=ts)


def inv():
    return ledger.inventory('a', 'u', SYMBOL)


# ── signed inventory ─────────────────────────────────────────────────────────

def test_a_buy_opens_a_signed_long_and_a_sell_closes_it():
    fill('o1', 65, 65 * 100.0)
    assert inv().net_quantity == 65 and inv().average_cost == pytest.approx(100.0)
    applied = fill('o2', 65, 65 * 120.0, side='SELL', source='exit')
    assert applied.accepted and applied.realized_delta == pytest.approx(65 * 20.0)
    assert inv().net_quantity == 0 and inv().realized_pnl == pytest.approx(1300.0)
    assert inv().average_cost == 0.0


def test_a_short_future_realizes_the_opposite_way_round():
    fill('o1', 50, 50 * 500.0, side='SELL', symbol='NIFTY26SEPFUT')
    holding = ledger.inventory('a', 'u', 'NIFTY26SEPFUT')
    assert holding.net_quantity == -50 and holding.average_cost == pytest.approx(500.0)
    fill('o2', 50, 50 * 480.0, side='BUY', symbol='NIFTY26SEPFUT', source='exit')
    # Covering a short 20 lower is a PROFIT, not a loss.
    assert ledger.inventory('a', 'u', 'NIFTY26SEPFUT').realized_pnl == pytest.approx(1000.0)


def test_a_sell_larger_than_the_holding_flips_the_side_at_the_new_price():
    fill('o1', 50, 50 * 100.0, symbol='NIFTY26SEPFUT')
    fill('o2', 80, 80 * 120.0, side='SELL', symbol='NIFTY26SEPFUT', source='exit')
    holding = ledger.inventory('a', 'u', 'NIFTY26SEPFUT')
    assert holding.net_quantity == -30
    assert holding.average_cost == pytest.approx(120.0)   # the surplus opened the short
    assert holding.realized_pnl == pytest.approx(50 * 20.0)


# ── the cases the old single-exit-price accumulator got wrong ────────────────

def test_a_partial_exit_books_its_pnl_instead_of_deferring_it():
    # The registry path books realized PnL once per POSITION, so a partial exit
    # booked NOTHING and set a reconciliation flag instead. Here each increment
    # settles as it arrives: 40 out at 130 is 1200 realized while 60 are still held.
    fill('o1', 100, 100 * 100.0)
    applied = fill('o2', 40, 40 * 130.0, side='SELL', source='exit')
    assert applied.realized_delta == pytest.approx(1200.0)
    holding = inv()
    assert holding.net_quantity == 60 and holding.average_cost == pytest.approx(100.0)
    assert holding.realized_pnl == pytest.approx(1200.0)
    assert not holding.reconciliation_required
    # …and the rest of the same order settles at its own, worse price.
    fill('o2', 100, 40 * 130.0 + 60 * 110.0, side='SELL', source='exit')
    assert inv().net_quantity == 0
    assert inv().realized_pnl == pytest.approx(1200.0 + 600.0)


def test_a_partial_cancel_books_only_what_filled():
    # 130 requested, 65 filled, then CANCELLED. The cancel repeats the cumulative
    # quantity it already reported; it must not book the requested size.
    fill('o1', 65, 65 * 100.0)
    applied = fill('o1', 65, 65 * 100.0, source='recovery')
    assert not applied.accepted and applied.reason == 'duplicate'
    assert inv().net_quantity == 65


def test_fees_reduce_realized_pnl_on_the_increment_that_incurred_them():
    fill('o1', 65, 65 * 100.0, fees=20.0)
    assert inv().realized_pnl == pytest.approx(-20.0)   # cost booked before any exit
    fill('o2', 65, 65 * 120.0, side='SELL', source='exit', fees=25.0)
    assert inv().realized_pnl == pytest.approx(1300.0 - 45.0)
    assert inv().fees == pytest.approx(45.0)


def test_a_cost_with_no_provenance_is_refused():
    # "0 because nobody asked the broker" and "0 because it was free" are not the
    # same claim, and only one of them may be recorded.
    with pytest.raises(ValueError, match='invalid_fees_source'):
        ledger.record(account_id='a', uid='u', symbol=SYMBOL, exchange='NFO',
                      side='BUY', order_id='o1', cumulative_quantity=65,
                      cumulative_value=6500.0, source='entry', fees=20.0)


def test_realized_pnl_is_gross_until_every_fill_has_broker_charges():
    fill('o1', 65, 65 * 100.0)
    fill('o2', 65, 65 * 120.0, side='SELL', source='exit')
    assert inv().realized_is_gross and inv().realized_pnl == pytest.approx(1300.0)
    ledger.apply_fees(account_id='a', uid='u', symbol=SYMBOL, order_id='o1', fees=30.0)
    assert inv().realized_is_gross          # the exit order is still uncosted
    ledger.apply_fees(account_id='a', uid='u', symbol=SYMBOL, order_id='o2', fees=45.0)
    assert not inv().realized_is_gross
    assert inv().fees == pytest.approx(75.0)
    assert inv().realized_pnl == pytest.approx(1300.0 - 75.0)


def test_restated_charges_replace_rather_than_quarantine():
    # Unlike a fill, charges are computed after the fact and are expected to be
    # revised. A better answer must not block the account.
    fill('o1', 65, 65 * 100.0)
    ledger.apply_fees(account_id='a', uid='u', symbol=SYMBOL, order_id='o1', fees=30.0)
    ledger.apply_fees(account_id='a', uid='u', symbol=SYMBOL, order_id='o1', fees=34.5)
    assert inv().fees == pytest.approx(34.5)
    assert not inv().reconciliation_required
    assert ledger.conflicts('u') == []


def test_charges_for_an_order_the_ledger_never_saw_change_nothing():
    fill('o1', 65, 65 * 100.0)
    assert ledger.apply_fees(account_id='a', uid='u', symbol=SYMBOL,
                             order_id='nosuchorder', fees=30.0) is None
    assert inv().fees == 0.0


def test_charges_land_once_on_a_multi_increment_order():
    # Charges are levied per ORDER. Splitting them across increments would invent
    # a precision the broker never reported.
    fill('o1', 40, 40 * 100.0)
    fill('o1', 100, 100 * 100.0)
    ledger.apply_fees(account_id='a', uid='u', symbol=SYMBOL, order_id='o1', fees=30.0)
    assert inv().fees == pytest.approx(30.0)
    assert [r['fees'] for r in ledger.increments('u')] == [0.0, 30.0]
    assert not inv().realized_is_gross


# ── duplicate, older and reordered evidence ──────────────────────────────────

def test_duplicate_cumulative_evidence_books_nothing_twice():
    fill('o1', 65, 65 * 100.0)
    before = inv().net_quantity
    for _ in range(5):
        applied = fill('o1', 65, 65 * 100.0)
        assert not applied.accepted and applied.reason == 'duplicate'
    assert inv().net_quantity == before
    assert len(ledger.increments('u')) == 1


def test_older_cumulative_evidence_is_ignored_without_flagging():
    fill('o1', 100, 100 * 100.0)
    applied = fill('o1', 40, 40 * 100.0)
    assert not applied.accepted and applied.reason == 'older_cumulative'
    assert inv().net_quantity == 100 and not inv().reconciliation_required


def test_concurrent_workers_book_one_increment_for_one_piece_of_evidence():
    def once(_):
        db.init()
        return fill('o1', 65, 65 * 100.0).accepted
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(once, range(16))) == 1
    assert inv().net_quantity == 65


def test_a_reordered_fill_is_replayed_into_its_true_position():
    # In exchange order: buy 100 @ 100, buy 100 @ 200 (avg 150), sell 100 @ 300
    # realizes 15000. Booked in ARRIVAL order it would realize 20000 and leave the
    # wrong average behind, which is exactly what a running total cannot recover from.
    fill('o1', 100, 100 * 100.0, ts=1_000)
    fill('o3', 100, 100 * 300.0, side='SELL', source='exit', ts=3_000)
    fill('o2', 100, 100 * 200.0, ts=2_000)
    holding = inv()
    assert holding.realized_pnl == pytest.approx(15_000.0)
    assert holding.net_quantity == 100 and holding.average_cost == pytest.approx(150.0)


def test_the_day_total_follows_the_replay_not_the_arrival_order():
    fill('o1', 100, 100 * 100.0, ts=1_000)
    fill('o3', 100, 100 * 300.0, side='SELL', source='exit', ts=3_000)
    day = ledger.ist_day(3_000)
    assert ledger.realized_pnl('u', day_iso=day) == pytest.approx(20_000.0)
    fill('o2', 100, 100 * 200.0, ts=2_000)
    assert ledger.realized_pnl('u', day_iso=day) == pytest.approx(15_000.0)


def test_realized_pnl_is_bucketed_by_the_ist_day_of_the_fill():
    fill('o1', 65, 65 * 100.0, ts=1_700_000_000_000)
    fill('o2', 65, 65 * 120.0, side='SELL', source='exit', ts=1_700_000_000_000)
    day = ledger.ist_day(1_700_000_000_000)
    assert ledger.realized_pnl('u', day_iso=day) == pytest.approx(1300.0)
    assert ledger.realized_pnl('u', day_iso='1999-01-01') == 0.0


# ── contradictions are quarantined, never applied and never dropped ──────────

def test_a_restated_value_for_the_same_quantity_is_quarantined():
    fill('o1', 65, 65 * 100.0)
    applied = fill('o1', 65, 65 * 111.0)
    assert not applied.accepted and applied.reason == 'cumulative_value_correction'
    assert applied.reconciliation_required
    holding = inv()
    assert holding.net_quantity == 65
    assert holding.average_cost == pytest.approx(100.0)  # the restatement was NOT applied
    assert holding.reconciliation_reason == 'cumulative_value_correction'
    assert [c['reason'] for c in ledger.conflicts('u')] == ['cumulative_value_correction']


def test_a_flag_survives_later_good_evidence_until_it_is_resolved():
    fill('o1', 65, 65 * 100.0)
    fill('o1', 65, 65 * 111.0)
    assert fill('o2', 65, 65 * 120.0, side='SELL', source='exit').accepted
    assert inv().reconciliation_required
    resolved = ledger.resolve('a', 'u', SYMBOL, note='')
    assert not resolved.reconciliation_required
    assert resolved.realized_pnl == pytest.approx(1300.0)


def test_one_order_id_cannot_carry_two_contracts():
    fill('o1', 65, 65 * 100.0)
    applied = fill('o1', 130, 130 * 100.0, symbol='NIFTY26SEP25100CE')
    assert applied.reason == 'order_identity_conflict'
    assert ledger.inventory('a', 'u', 'NIFTY26SEP25100CE').net_quantity == 0
    assert inv().net_quantity == 65


def test_a_cumulative_increase_that_adds_no_value_is_quarantined():
    fill('o1', 65, 65 * 100.0)
    applied = fill('o1', 130, 65 * 100.0)
    assert applied.reason == 'nonpositive_incremental_value'
    assert inv().net_quantity == 65 and inv().reconciliation_required


@pytest.mark.parametrize('kwargs', [
    dict(side='BUYY'), dict(source='guess'), dict(order_id=''),
    dict(cumulative_value=float('nan')), dict(cumulative_quantity=-1),
    dict(fees=-1.0), dict(account_id=''),
])
def test_unusable_evidence_raises_rather_than_booking_something_wrong(kwargs):
    base = dict(account_id='a', uid='u', symbol=SYMBOL, exchange='NFO', side='BUY',
                order_id='o1', cumulative_quantity=65, cumulative_value=6500.0,
                source='entry')
    with pytest.raises(ValueError):
        ledger.record(**{**base, **kwargs})
    assert ledger.increments('u') == []


# ── crash ────────────────────────────────────────────────────────────────────

def test_a_crash_between_the_fill_and_its_projection_books_neither(monkeypatch):
    fill('o1', 100, 100 * 100.0)
    original = ledger._project

    def explode(conn, *a, **kw):
        raise RuntimeError('power cut')

    monkeypatch.setattr(ledger, '_project', explode)
    with pytest.raises(RuntimeError):
        fill('o2', 40, 40 * 130.0, side='SELL', source='exit')
    monkeypatch.setattr(ledger, '_project', original)
    # Neither the quantity nor its realized value survived: the exit is simply
    # unbooked, and replaying the same evidence completes it.
    assert inv().net_quantity == 100
    assert len(ledger.increments('u')) == 1
    assert fill('o2', 40, 40 * 130.0, side='SELL', source='exit').accepted
    assert inv().net_quantity == 60


def test_holdings_lists_open_and_flagged_positions_only():
    fill('o1', 65, 65 * 100.0)
    fill('o2', 65, 65 * 120.0, side='SELL', source='exit')
    assert ledger.holdings('u') == []
    fill('o3', 65, 65 * 100.0, symbol='NIFTY26SEP25100CE')
    assert [h.symbol for h in ledger.holdings('u')] == ['NIFTY26SEP25100CE']


def test_lots_are_reported_only_when_a_fill_told_us_the_lot_size():
    fill('o1', 100, 100 * 100.0)
    assert inv().lot_size == 0 and inv().net_lots is None
    ledger.record(account_id='a', uid='u', symbol=SYMBOL, exchange='NFO', side='BUY',
                  order_id='o2', cumulative_quantity=50, cumulative_value=50 * 100.0,
                  source='entry', lot_size=50)
    assert inv().lot_size == 50 and inv().net_lots == 3


def test_a_smaller_quantity_worth_more_money_is_quarantined():
    fill('o1', 100, 100 * 100.0)
    applied = fill('o1', 40, 40 * 300.0)
    assert applied.reason == 'nonmonotonic_cumulative_value'
    assert inv().net_quantity == 100 and inv().reconciliation_required
    assert inv().average_cost == pytest.approx(100.0)
