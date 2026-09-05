"""Safety regression fixtures test mechanics; never used as market-performance data."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import asyncio
import numpy as np
import pytest

from app.domain.models import Candle
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime
from app.engines.sterling_kite_engine.exits import trail_exit_index
from app.services.kite_engine import market_hours as mh, scanner, sizing, monitor, positions, state, service
from app.services.kite_engine import backtest as bt

IST = ZoneInfo('Asia/Kolkata')
def dt(day='2026-09-07', clock='10:15'):
    return datetime.fromisoformat(day+'T'+clock).replace(tzinfo=IST)

@pytest.mark.parametrize('clock,phase', [
 ('09:00','preopen_market_limit'),('09:05','preopen_limit'),
 ('09:08','preopen_random_or_matching'),('09:10','preopen_matching'),
 ('09:12','preopen_buffer'),('09:15','continuous'),('15:39','continuous'),('15:40','closed')])
def test_preopen_boundaries(clock, phase):
    assert mh.session_phase(dt(clock=clock)) == phase
    assert mh.is_market_open(dt(clock=clock)) == (phase == 'continuous')

@pytest.mark.parametrize('clock,phase', [('15:15','cas_transition'),('15:20','cas_market_limit'),
 ('15:25','cas_limit'),('15:28','cas_random_or_matching'),('15:30','cas_matching'),('15:35','closed')])
def test_cash_auction_never_continuous(clock, phase):
    assert mh.session_phase(dt(clock=clock), exchange='NSE', cas_eligible=True) == phase
    assert not mh.is_market_open(dt(clock=clock), exchange='NSE', cas_eligible=True)
    assert mh.is_market_open(dt(clock=clock), exchange='NFO')

def test_effective_dates_holidays_unknown_and_naive():
    assert not mh.is_market_open(dt('2026-07-31','15:30'))
    assert mh.is_market_open(dt('2026-08-03','15:30'))
    assert not mh.is_market_open(dt('2026-09-14'))
    assert not mh.is_market_open(dt('2026-09-05'))
    assert mh.session_phase(dt('2027-01-04')) == 'calendar_unknown'
    with pytest.raises(ValueError): mh.is_market_open(datetime(2026,9,7,10))
    assert mh.session_phase(dt().astimezone(ZoneInfo('UTC'))) == 'continuous'

def test_cash_signal_cutoff_and_buffer():
    assert mh.entry_block_reason(dt(clock='15:15'), cash_signal=True) == 'cash_signal_auction'
    assert mh.entry_block_reason(dt(clock='15:14'),cash_signal=True,buffer_minutes=1) == 'entry_close_buffer'
    assert not mh.entry_block_reason(dt(clock='15:30'))

def bar(clock, **kw):
    return Candle(timestamp_ms=int(dt(clock=clock).timestamp()*1000),
                  open=100, high=110, low=90, close=105, volume=10, **kw)

def test_all_forming_bars_and_cash_auction_removed():
    bars=[bar('14:15'),bar('15:15')]
    assert scanner.drop_forming(bars, int(dt(clock='15:15').timestamp()*1000),
                                exchange='NSE',cas_eligible=True) == bars[:1]
    assert scanner.drop_forming(bars, int(dt(clock='15:39').timestamp()*1000),exchange='NFO') == bars[:1]
    assert scanner.drop_forming(bars, int(dt(clock='15:40').timestamp()*1000),exchange='NFO') == bars
    assert scanner.drop_forming(bars+[bar('15:20')], int(dt(clock='15:22').timestamp()*1000),exchange='NFO') == bars[:1]

def test_malformed_bars_never_repaired_into_signals():
    b=bar('10:15'); now=int(dt(clock='13:15').timestamp()*1000)
    assert scanner.drop_forming([b,b],now) == []
    b.low=120
    assert scanner.drop_forming([b],now) == []

@pytest.mark.parametrize('field,value',[('available_capital',0),('available_capital',float('nan')),
 ('stop_premium',100),('stop_premium',120),('stop_premium',0),('entry_premium',float('inf')),
 ('lot_size',0),('lot_size',1.2)])
def test_sizing_unknown_invalid_blocks(field,value):
    kw=dict(entry_premium=100,stop_premium=80,lot_size=50,available_capital=500_000,risk_pct=1,max_lots=10)
    kw[field]=value
    r=sizing.size_position(**kw)
    assert r.blocked and r.qty == 0

def test_risk_override_never_overrides_affordability():
    r=sizing.size_position(entry_premium=100,stop_premium=80,lot_size=50,
                          available_capital=100,risk_pct=1,max_lots=10,allow_min_lot_over_risk=True)
    assert r.blocked and r.qty == 0

def test_raw_extrema_carried_separately():
    x=np.arange(100,200,2,dtype=float)
    r=compute_regime(x,x+2,x-2,x+1,SterlingKiteEngineConfig())
    assert np.array_equal(r.raw_low,x-2)
    assert not np.array_equal(r.raw_low,r.basis_low)

def test_synthetic_ha_touch_cannot_trigger_real_stop():
    r=SimpleNamespace(raw_low=np.array([100.,100.]),raw_high=np.array([110.,110.]),
        basis_low=np.array([80.,80.]),basis_high=np.array([110.,110.]),
        best_trail_line_value=lambda direction,j:90.,line=lambda target:np.array([90.,90.]))
    assert trail_exit_index(r,'long',0,1,SterlingKiteEngineConfig()) is None
    r.raw_low[1]=89
    assert trail_exit_index(r,'long',0,1,SterlingKiteEngineConfig()) == 1


@pytest.mark.parametrize('direction,levels,expected', [
    ('long',[90.,100.,95.,95.],100.), ('short',[110.,100.,105.,105.],100.)])
def test_reported_stop_and_exit_reason_keep_intervening_ratchet(direction,levels,expected):
    from app.engines.sterling_kite_engine.exits import reported_trail_level, resolve_exit
    r=SimpleNamespace(raw_low=np.array([100.,105.,101.,98.]),
        raw_high=np.array([100.,95.,99.,102.]),
        best_trail_line_value=lambda direction,j:levels[j],
        red_line_count=lambda direction,j:0)
    cfg=SterlingKiteEngineConfig()
    assert reported_trail_level(r,direction,0,None,2,cfg) == expected
    assert reported_trail_level(r,direction,0,3,3,cfg) == expected
    idx,reason=resolve_exit(r,direction,0,3,cfg,np.zeros(4,dtype=bool),np.zeros(4,dtype=bool))
    assert idx == 3 and f'{expected:.2f}' in reason

def test_replay_enters_next_raw_open(monkeypatch):
    n=30; o=np.arange(n,dtype=float)+100; c=o+1
    monkeypatch.setattr(bt,'entry_transitions',lambda r:(np.arange(n)==23,np.zeros(n,dtype=bool)))
    monkeypatch.setattr(bt,'_exit_bar',lambda *a:(26,'red count exit'))
    run=bt.replay_premium_series(timestamps_ms=list(range(n)),premium_open=o,
        premium_high=c+1,premium_low=o-1,premium_close=c,cfg=SterlingKiteEngineConfig(),
        trail_target='fast',qty=1,costs=bt.OptionCosts(),starting_capital=10000)
    assert run.trades[0].entry_ms == 24 and run.trades[0].entry_premium == o[24]
    assert run.trades[0].exit_ms == 27 and run.trades[0].exit_premium == o[27]

class ExitBroker:
    calls=0
    async def place_order_option(self,*args,**kw):
        self.calls+=1
        return {'order_id':'exit1'}
    async def get_positions_raw(self):
        return {'net':[{'tradingsymbol':'OPT','quantity':50}]}


@pytest.mark.asyncio
@pytest.mark.parametrize('direction,quantity',[('long',-50),('short',50)])
async def test_exit_never_increases_opposite_broker_exposure(direction,quantity):
    uid='audit_direction_'+direction; positions.reset(uid); monitor.forget_holdings(uid)
    p=positions.register(positions.OpenPosition(uid=uid,symbol='OPT',exchange='NFO',qty=50,
        direction=direction,status=positions.OPEN,stop_premium=80))
    class OppositeBroker(ExitBroker):
        async def get_positions_raw(self):
            return {'net':[{'tradingsymbol':'OPT','quantity':quantity}]}
    broker=OppositeBroker()
    assert not await monitor._exit_position(broker,uid,p,80)
    assert broker.calls == 0 and p.status == positions.OPEN
    assert p.pnl_reconciliation_required

@pytest.mark.asyncio
async def test_ack_is_not_fill_and_pending_survives_reload(monkeypatch):
    uid='audit_ack'; positions.reset(uid); state.reset(uid)
    persisted={}
    monkeypatch.setattr(positions.db,'set_config',lambda key,value:persisted.__setitem__(key,value))
    monkeypatch.setattr(positions.db,'get_config',lambda key:persisted.get(key))
    p=positions.register(positions.OpenPosition(uid=uid,symbol='OPT',exchange='NFO',qty=50,
        entry_premium=100,fill_price=100,stop_premium=80,status=positions.OPEN,order_id='entry'))
    broker=ExitBroker()
    assert await monitor._exit_position(broker,uid,p,79)
    positions.reset(uid)
    p=positions.get(uid,'OPT')
    assert p.status == positions.OPEN and p.exit_order_id == 'exit1'
    assert state.daily_realized_pnl(uid) == 0
    assert not await monitor._exit_position(broker,uid,p,78)
    assert broker.calls == 1
    event=dict(tradingsymbol='OPT',transaction_type='SELL',order_id='exit1',status='COMPLETE',filled_quantity=50,average_price=81)
    await monitor.on_order_update(uid,event)
    assert p.status == positions.CLOSED and state.daily_realized_pnl(uid) == -950
    await monitor.on_order_update(uid,event)
    assert state.daily_realized_pnl(uid) == -950

@pytest.mark.asyncio
async def test_partial_duplicate_and_rejected_exit_keeps_remainder():
    uid='audit_partial'; positions.reset(uid);state.reset(uid)
    p=positions.register(positions.OpenPosition(uid=uid,symbol='OPT',exchange='NFO',qty=50,
        entry_premium=100,fill_price=100,stop_premium=80,status=positions.OPEN,exit_order_id='exit1'))
    event=dict(tradingsymbol='OPT',transaction_type='SELL',order_id='exit1',status='OPEN',filled_quantity=20,average_price=81)
    await monitor.on_order_update(uid,event)
    await monitor.on_order_update(uid,event)
    assert p.qty == 30 and p.status == positions.OPEN
    await monitor.on_order_update(uid,{**event,'status':'CANCELLED'})
    assert p.qty == 30 and p.status == positions.OPEN and p.exit_order_id == ""

@pytest.mark.asyncio
async def test_unknown_other_order_never_closes_position():
    uid='audit_other';positions.reset(uid)
    p=positions.register(positions.OpenPosition(uid=uid,symbol='OPT',exchange='NFO',qty=50,status=positions.OPEN))
    await monitor.on_order_update(uid,dict(tradingsymbol='OPT',transaction_type='SELL',order_id='unrelated',status='COMPLETE',filled_quantity=50,average_price=81))
    assert p.status == positions.OPEN

def test_statutory_stt_change_is_date_effective():
    costs=bt.OptionCosts(slippage_pct=0)
    a=costs.round_trip(100,100,100,exit_ms=int(dt('2026-03-31').timestamp()*1000))
    b=costs.round_trip(100,100,100,exit_ms=int(dt('2026-04-01').timestamp()*1000))
    assert b-a == pytest.approx(5)


@pytest.mark.parametrize("quote", [None, {}, {"oi":float("nan")}, {"oi":100,"depth":{"buy":[{"price":110}],"sell":[{"price":100}]}}])
def test_enabled_liquidity_gate_fails_closed(quote):
    assert service._passes_liquidity(quote,5,100)[0] is False

@pytest.mark.asyncio
async def test_accepted_exit_timeout_recovers_by_unique_tag_without_resend():
    uid='audit_timeout'; positions.reset(uid); state.reset(uid)
    p=positions.register(positions.OpenPosition(uid=uid,symbol='OPT',exchange='NFO',qty=50,
        entry_premium=100,fill_price=100,stop_premium=80,status=positions.OPEN,order_id='entry'))
    class AcceptedTimeout(ExitBroker):
        async def place_order_option(self,*a,**kw):
            self.calls+=1
            self.tag=kw['tag']
            raise TimeoutError('response lost after acceptance')
        async def get_orders(self):
            return [dict(tag=self.tag,tradingsymbol='OPT',exchange='NFO',transaction_type='SELL',
                order_id='accepted-exit',status='COMPLETE',filled_quantity=50,average_price=82)]
    broker=AcceptedTimeout()
    assert not await monitor._exit_position(broker,uid,p,80)
    assert p.exit_order_id == 'unknown' and len(p.exit_tag) == 20 and p.exit_tag.isalnum()
    await service._reconcile_pending_positions(broker,uid)
    assert p.status == positions.CLOSED and broker.calls == 1
    assert state.daily_realized_pnl(uid) == -900
