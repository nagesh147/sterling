import asyncio
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
from app.services.exchanges import instrument_registry
from app.api.v1.endpoints.derivatives import _option_chain_or_none

class MockApp:
    state = type('State', (), {'adapter': None})()

async def main():
    app = MockApp()
    adapter = DeltaIndiaAdapter(api_key="", api_secret="", is_paper=False)
    app.state.adapter = adapter
    inst = instrument_registry.get_instrument("ETH")
    spot = await adapter.get_spot_price(inst)
    chain = await _option_chain_or_none(underlying="ETH", app=app, spot=spot)
    same_expiry = [o for o in chain if o.expiry_date == "030626"]
    
    total_oi = sum(o.open_interest for o in same_expiry)
    print(f"Total OI for 030626: {total_oi}")
    oi_by_strike = {}
    for o in same_expiry:
        oi_by_strike[o.strike] = oi_by_strike.get(o.strike, 0.0) + o.open_interest
    
    print("OI by strike:")
    for k, v in oi_by_strike.items():
        if v > 0:
            print(f"  {k}: {v}")

asyncio.run(main())
