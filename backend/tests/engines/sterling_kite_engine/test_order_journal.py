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
