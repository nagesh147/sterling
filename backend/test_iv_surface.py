import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
from app.services.exchanges.instrument_registry import get_instrument
from app.engines.backtest.iv_surface_fit import IVSurface

async def main():
    inst = get_instrument("BTC")
    adapter = DeltaIndiaAdapter(api_key="", api_secret="")
    options = await adapter.get_option_chain(inst)
    await adapter.close()
    
    strikes = [o.strike for o in options]
    dtes = [o.dte for o in options]
    ivs = [o.mark_iv for o in options]
    
    surface = IVSurface()
    surface.fit(strikes, dtes, ivs, 95000.0) # approx spot
    
    # Test predictions
    print("ATM 7-DTE IV:", surface.predict(95000.0, 95000.0, 7))
    print("OTM 7-DTE Call (Strike=100k):", surface.predict(100000.0, 95000.0, 7))

asyncio.run(main())
