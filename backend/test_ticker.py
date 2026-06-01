import asyncio
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
from app.services.exchanges import instrument_registry

async def main():
    adapter = DeltaIndiaAdapter(api_key="", api_secret="", is_paper=False)
    inst = instrument_registry.get_instrument("ETH")
    spot = await adapter.get_spot_price(inst)
    print(f"SPOT: {spot}")

asyncio.run(main())
