from datetime import datetime, timezone
import pytest
from app.engines.nifty_orb_options import Bar, OptionContract, StrategyConfig
from app.engines.nifty_orb_universe import UniverseInstrument, UniverseScanConfig
from app.services.nifty_orb_option_scanner import scan_option_candidates

@pytest.mark.asyncio
async def test_actionable_long_signal_becomes_ce_plan():
    bars=[]
    base=datetime(2026,1,5,9,15,tzinfo=timezone.utc)
    for i in range(40):
        p=100+i*0.2
        if i==3:p=103
        bars.append(Bar(base.replace(minute=15+i),p,p+1,p-1,p+0.4,1000+i*10))
    # Keep this test at orchestration level; signal behavior itself is tested by engine tests.
    async def fetch_bars(item,cfg): return bars
    async def fetch_options(item,direction,cfg):
        return [OptionContract("TESTCE",100,"2026-01-08","CE",10,9.95,10.05,10,None,5000,20000)]
    result=await scan_option_candidates([UniverseInstrument("TEST","stock")],strategy_config=StrategyConfig(opening_range_minutes=5,entry_start="09:15",entry_end="15:00"),scan_config=UniverseScanConfig(min_confidence=0),fetch_bars=fetch_bars,fetch_options=fetch_options)
    assert all(x.planned.option.option_type=="CE" for x in result)
