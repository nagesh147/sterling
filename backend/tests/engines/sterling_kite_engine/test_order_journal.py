from concurrent.futures import ThreadPoolExecutor
import pytest

from app.services import db
from app.services.kite_engine import order_journal as journal
from app.services.kite_engine import monitor, positions, state


@pytest.fixture(autouse=True)
def isolated_journal():
    prior=db._available
    db.init(); journal.clear_for_tests('u'); positions.reset('u'); state.reset('u')
    yield
    journal.clear_for_tests('u'); positions.reset('u'); state.reset('u'); db._available=prior


def args():
    return dict(uid='u',account_id='a',strategy_id='sterling-kite',generation_id='g1',
      signal_id='s1',exchange='NFO',symbol='NIFTY26SEP25000CE',side='BUY',quantity=65,
      payload={'stop':100})


def test_reservation_is_atomic_and_idempotent():
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows=list(pool.map(lambda _:journal.reserve(**args()),range(16)))
    assert len({r.intent_key for r in rows}) == 1
    assert len({r.tag for r in rows}) == 1 and len(rows[0].tag) == 20
    assert len(journal.unresolved('u')) == 1


def test_only_one_worker_can_claim_network_submission():
    r = journal.reserve(**args())
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: journal.claim_submission(r.intent_key), range(32)))
    assert sum(claims) == 1
    with pytest.raises(ValueError, match="use_claim_submission"):
        journal.transition(r.intent_key, "SUBMITTING")


def test_configuration_change_cannot_reexecute_signal():
    first = journal.reserve(**args())
    second = journal.reserve(**{**args(), "generation_id": "new-config"})
    assert first.intent_key == second.intent_key
    with pytest.raises(ValueError, match="immutable_intent_conflict"):
        journal.reserve(**{**args(), "quantity": 130})


def test_pending_capital_reservations_serialize_across_workers():
    def reserve_one(n):
        try:
            journal.reserve(**{**args(), "signal_id": str(n)},
                            capital_required=60, available_capital=100)
            return True
        except ValueError as exc:
            assert str(exc) == "insufficient_unreserved_capital"
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve_one, range(16))) == 1


def test_lost_ack_uses_tag_fallback_with_account_scope():
    r = journal.reserve(**args())
    journal.claim_submission(r.intent_key)
    journal.submission_uncertain(r.intent_key, "timeout")
    assert journal.find(uid="u", account_id="a", order_id="new-id", tag=r.tag) == journal.unresolved("u")[0]
    assert journal.find(uid="u", account_id="other", order_id="new-id", tag=r.tag) is None


def test_out_of_order_cumulative_fills_never_regress_or_double_count():
    r = journal.reserve(**args())
    journal.claim_submission(r.intent_key)
    first = journal.observe_order(r.intent_key, status="OPEN", order_id="o", filled_quantity=40, average_price=100)
    old = journal.observe_order(r.intent_key, status="OPEN", order_id="o", filled_quantity=20, average_price=99)
    assert first.delta_quantity == 40 and old.delta_quantity == 0
    assert old.intent.filled_quantity == 40 and not old.reconciliation_required
    conflict = journal.observe_order(r.intent_key, status="OPEN", order_id="o", filled_quantity=40, average_price=101)
    assert conflict.reconciliation_required and conflict.intent.filled_value == 4000


def test_projection_ack_cannot_clear_newer_fill():
    r = journal.reserve(**args())
    journal.claim_submission(r.intent_key)
    first = journal.observe_order(r.intent_key, status="OPEN", order_id="o", filled_quantity=20, average_price=100)
    second = journal.observe_order(r.intent_key, status="COMPLETE", order_id="o", filled_quantity=65, average_price=101)
    assert not journal.mark_projected(r.intent_key, first.intent.projection_version)
    assert journal.pending_projection("u", "a")
    assert journal.mark_projected(r.intent_key, second.intent.projection_version)
    assert not journal.pending_projection("u", "a")


def test_ack_and_timeout_do_not_regress_early_fill_postback():
    r = journal.reserve(**args())
    journal.claim_submission(r.intent_key)
    journal.observe_order(r.intent_key, status="COMPLETE", order_id="o", filled_quantity=65, average_price=101)
    assert journal.acknowledge(r.intent_key, "o").state == "FILLED"
    assert journal.submission_uncertain(r.intent_key, "timeout").state == "FILLED"


def test_state_machine_rejects_terminal_resurrection():
    r=journal.reserve(**{**args(),'signal_id':'s2'})
    assert journal.claim_submission(r.intent_key)
    journal.transition(r.intent_key,'SUBMITTED',order_id='O1')
    journal.observe_order(r.intent_key, status='COMPLETE', order_id='O1',
                          filled_quantity=65, average_price=101.5)
    with pytest.raises(ValueError): journal.transition(r.intent_key,'SUBMITTED')


def test_fill_event_is_exactly_once():
    kw=dict(account_id='a',order_id='O1',trade_id='T1',uid='u',symbol='OPT',
            side='BUY',quantity=65,price=101.5,raw={'exchange_trade_id':'T1'})
    assert journal.record_fill(**kw)
    assert not journal.record_fill(**kw)


def test_find_by_order_or_tag():
    r=journal.reserve(**{**args(),'signal_id':'s3'})
    assert journal.claim_submission(r.intent_key)
    r=journal.transition(r.intent_key,'SUBMITTED',order_id='O3')
    assert journal.find(uid='u',account_id='a',order_id='O3').tag == r.tag
    assert journal.find(uid='u',account_id='a',tag=r.tag).order_id == 'O3'


class _LiveClient:
    """Minimal live client. The journal is only consulted for LIVE orders — a
    paper run never reserves an intent — so `on_order_update` routes to
    `execution_lifecycle.consume_order` only when a non-paper client is passed,
    and every production caller passes one (the ticker's order broadcaster, the
    engine's own post-submit reconcile, and the monitor's recovery sweep)."""
    _is_paper = False
    _account_id = 'a'


@pytest.mark.asyncio
async def test_confirmed_entry_fill_closes_durable_intent():
    r=journal.reserve(**{**args(),'signal_id':'s4'})
    assert journal.claim_submission(r.intent_key)
    journal.transition(r.intent_key,'SUBMITTED',order_id='O4')
    # `account_id` must match the intent's, or the postback is not attributable
    # to it; `stop_mode='monitor'` keeps broker protection out of this test.
    positions.register(positions.OpenPosition(uid='u',account_id='a',symbol=args()['symbol'],
        exchange='NFO',qty=65,lot_size=65,entry_premium=120,stop_premium=100,
        order_id='O4',stop_mode='monitor'))
    # The persisted contract and the broker's echo must agree on every identity
    # field, so the postback carries exchange, product and quantity too.
    await monitor.on_order_update('u',dict(tradingsymbol=args()['symbol'],order_id='O4',
        exchange='NFO',product='NRML',quantity=65,
        transaction_type='BUY',status='COMPLETE',filled_quantity=65,average_price=121),
        client=_LiveClient())
    assert journal.find(uid='u',account_id='a',order_id='O4').state == 'FILLED'
    p = positions.get('u', args()['symbol'])
    assert p.status == positions.OPEN and p.qty == 65
