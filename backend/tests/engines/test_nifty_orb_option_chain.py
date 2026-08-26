from datetime import date
from app.engines.nifty_orb_options import StrategyConfig
from app.services.nifty_orb_option_chain import filter_chain, normalize_chain

def test_normalize_chain_supports_common_payload_names():
    contracts=normalize_chain([{"tradingsymbol":"NIFTY26JAN25000CE","strike_price":25000,"expiry_date":"2026-01-29","instrument_type":"CE","last_price":120,"bid_price":119,"ask_price":121,"lotsize":75,"volume":5000,"oi":25000}])
    assert len(contracts)==1
    assert contracts[0].option_type=="CE"
    assert contracts[0].lot_size==75

def test_filter_chain_rejects_wide_spread_and_illiquidity():
    contracts=normalize_chain([{"symbol":"CE","strike":25000,"expiry":"2026-01-22","option_type":"CE","ltp":100,"bid":90,"ask":110,"lot_size":75,"volume":5000,"oi":25000}])
    cfg=StrategyConfig(expiry_dte_min=0,expiry_dte_max=30,max_spread_pct=5,min_option_volume=1000,min_open_interest=10000)
    assert filter_chain(contracts,cfg,today=date(2026,1,1))==[]

def test_filter_chain_enforces_expiry_and_liquidity():
    contracts=normalize_chain([{"symbol":"CE","strike":25000,"expiry":"2026-01-08","option_type":"CE","ltp":100,"bid":99,"ask":101,"lot_size":75,"volume":5000,"oi":25000}])
    cfg=StrategyConfig(expiry_dte_min=0,expiry_dte_max=30,max_spread_pct=5,min_option_volume=1000,min_open_interest=10000)
    assert len(filter_chain(contracts,cfg,today=date(2026,1,1)))==1
