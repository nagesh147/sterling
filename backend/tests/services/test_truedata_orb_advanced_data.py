import pytest
from datetime import datetime, timezone, timedelta
from app.engines.nifty_orb_options import OptionContract, StrategyConfig
from app.services.providers.truedata.orb_provider import TrueDataOrbProvider

class FakeTrueData:
    def __init__(self, tick): self.tick=tick
    async def get_last_ticks(self, symbol, n, **kwargs): return [self.tick] if self.tick else []

@pytest.mark.asyncio
async def test_truedata_refresh_rejects_stale_quote():
    stale=(datetime.now(timezone.utc)-timedelta(minutes=2)).strftime('%Y-%m-%dT%H:%M:%S+00:00')
    provider=TrueDataOrbProvider(FakeTrueData({'timestamp':stale,'ltp':10,'bid':9.9,'ask':10.1,'volume':5000,'oi':20000}))
    c=OptionContract('NIFTY26AUG25000CE',25000,'2026-08-27','CE',10,9.9,10.1,65,None,5000,20000)
    out=await provider.refresh_contract(c,StrategyConfig(max_quote_staleness_s=15))
    assert out==[]

@pytest.mark.asyncio
async def test_truedata_refresh_can_disable_tick_validation():
    provider=TrueDataOrbProvider(FakeTrueData(None))
    c=OptionContract('NIFTY26AUG25000CE',25000,'2026-08-27','CE',10,9.9,10.1,65,None,5000,20000)
    cfg=StrategyConfig(truedata_use_ticks=False,truedata_use_quote_freshness=False)
    out=await provider.refresh_contract(c,cfg)
    assert len(out)==1
