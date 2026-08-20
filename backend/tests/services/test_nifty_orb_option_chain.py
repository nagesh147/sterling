from app.engines.nifty_orb_options import OptionContract, StrategyConfig
from app.services.nifty_orb_option_chain import filter_chain, normalize_chain


def test_normalize_chain_returns_engine_contracts():
    rows=[{'symbol':'NIFTY26AUG25000CE','strike':25000,'expiry':'2026-08-27','option_type':'CE','ltp':100,'bid':99,'ask':101,'lot_size':75,'volume':5000,'oi':50000,'delta':0.5}]
    contracts=normalize_chain(rows)
    assert len(contracts)==1
    assert isinstance(contracts[0],OptionContract)
    assert contracts[0].symbol=='NIFTY26AUG25000CE'


def test_filter_chain_honors_truedata_switches():
    # 1.0% spread: inside the 1.5% ceiling, so open interest is the only gate under test.
    contract=OptionContract('CE',25000,'2026-08-27','CE',100,99.5,100.5,75,0.5,5000,50000)
    strict=StrategyConfig(min_open_interest=100000,truedata_use_oi=True,max_spread_pct=1.5)
    loose=StrategyConfig(min_open_interest=100000,truedata_use_oi=False,max_spread_pct=1.5)
    assert filter_chain([contract],strict)==[]
    assert filter_chain([contract],loose)==[contract]
