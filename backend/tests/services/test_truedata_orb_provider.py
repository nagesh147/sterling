import pytest
from app.engines.nifty_orb_options import StrategyConfig
from app.services.providers.truedata.orb_provider import TrueDataOrbProvider

class FakeClient:
    async def get_last_bars(self,symbol,n,**kwargs):
        return [{"timestamp":"2026-08-19 09:15:00","open":100,"high":101,"low":99,"close":100.5,"volume":1000,"oi":10}]
    async def get_last_ticks(self,symbol,n,**kwargs):
        return [{"timestamp":"2026-08-19 09:30:00","ltp":101,"volume":2000,"oi":20,"bid":100.9,"bidqty":100,"ask":101.1,"askqty":100}]
    async def get_option_chain(self,symbol,expiry):
        return {"Records":[{"symbol":"TEST26AUG100CE","strike":100,"expiry":"2026-08-27","option_type":"CE","ltp":5,"bid":4.95,"ask":5.05,"lot_size":10,"volume":5000,"oi":20000}]}

@pytest.mark.asyncio
async def test_truedata_provider_maps_one_minute_bars():
    bars=await TrueDataOrbProvider(FakeClient()).bars("TEST",StrategyConfig())
    assert len(bars)==1 and bars[0].close==100.5

@pytest.mark.asyncio
async def test_truedata_provider_exposes_bid_ask_tick():
    tick=await TrueDataOrbProvider(FakeClient()).latest_tick("TEST")
    assert tick["bid"]==100.9 and tick["ask"]==101.1

@pytest.mark.asyncio
async def test_truedata_provider_normalizes_option_chain():
    contracts=await TrueDataOrbProvider(FakeClient()).option_chain("TEST","2026-08-27",StrategyConfig(expiry_dte_max=30,min_option_volume=1000,min_open_interest=10000,truedata_use_quote_freshness=False))
    assert contracts[0].option_type=="CE"
