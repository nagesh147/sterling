import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
from app.services.exchanges.instrument_registry import get_instrument

async def main():
    inst = get_instrument("BTC")
    if not inst:
        print("BTC instrument not found")
        return
        
    adapter = DeltaIndiaAdapter(api_key="", api_secret="")
    options = await adapter.get_option_chain(inst)
    print(f"Found {len(options)} options for BTC")
    
    if options:
        opt = options[0]
        print(opt)
        
    await adapter.close()

asyncio.run(main())
