from datetime import datetime, timedelta
from app.engines.nifty_orb_options import Bar, OptionContract, StrategyConfig, generate_signal, select_option, build_trade_plan


def _bars(direction='LONG'):
    start=datetime(2026,8,19,9,15)
    bars=[]
    price=100.0
    for i in range(40):
        ts=start+timedelta(minutes=5*i)
        high=price+0.8; low=price-0.8; close=price+0.4
        if i>=3 and direction=='LONG':
            close=103.0+i*0.15; high=close+0.5; low=close-0.4
        if i>=3 and direction=='SHORT':
            close=97.0-i*0.15; high=close+0.4; low=close-0.5
        bars.append(Bar(ts,price,high,low,close,1000+i*100))
        price=close
    return bars


def test_long_signal_maps_to_ce_only():
    cfg=StrategyConfig(opening_range_minutes=15,entry_start='09:30',entry_end='15:00',volume_multiplier=1.0,max_risk_inr=25000)
    signal=generate_signal(_bars('LONG'),cfg)
    assert signal.direction=='LONG'
    option=OptionContract('NIFTYCE',100,'2026-08-27','CE',100,99,101,75,0.5,5000,50000)
    plan=build_trade_plan(signal,option,cfg,spot=103)
    assert plan.option_type=='CE'
    assert plan.quantity % option.lot_size == 0
    assert plan.quantity > 0


def test_short_signal_maps_to_pe_only():
    cfg=StrategyConfig(opening_range_minutes=15,entry_start='09:30',entry_end='15:00',volume_multiplier=1.0,max_risk_inr=25000)
    signal=generate_signal(_bars('SHORT'),cfg)
    assert signal.direction=='SHORT'
    option=OptionContract('NIFTYPE',100,'2026-08-27','PE',100,99,101,75,0.5,5000,50000)
    plan=build_trade_plan(signal,option,cfg,spot=96)
    assert plan.option_type=='PE'


def test_selection_respects_dte_and_liquidity():
    cfg=StrategyConfig(expiry_dte_min=0,expiry_dte_max=7,min_option_volume=1000,min_open_interest=10000,max_spread_pct=1.5)
    contracts=[
        OptionContract('BAD',100,'2026-08-27','CE',10,8,12,75,0.5,100,100),
        OptionContract('GOOD',100,'2026-08-27','CE',10,9.95,10.05,75,0.5,5000,50000),
    ]
    selected=select_option(100,'LONG',contracts,cfg)
    assert selected.symbol=='GOOD'


def test_option_direction_mismatch_is_rejected():
    # Same window as the other signals in this module: _bars() runs to 12:30 IST.
    cfg=StrategyConfig(opening_range_minutes=15,entry_start='09:30',entry_end='15:00',volume_multiplier=1.0)
    signal=generate_signal(_bars('LONG'),cfg)
    assert signal.direction=='LONG'
    option=OptionContract('PE',100,'2026-08-27','PE',10,9.9,10.1,75,0.5,5000,50000)
    try:
        build_trade_plan(signal,option,cfg,spot=103)
    except ValueError as exc:
        assert 'direction' in str(exc)
    else:
        raise AssertionError('Expected CE/PE direction mismatch to be rejected')
