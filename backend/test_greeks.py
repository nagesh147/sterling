import asyncio
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
from app.services.exchanges import instrument_registry
from pprint import pprint

async def main():
    adapter = DeltaIndiaAdapter(api_key="", api_secret="", is_paper=False)
    inst = instrument_registry.get_instrument("ETH")
    chain = await adapter.get_option_chain(inst)
    for c in chain:
        if c.strike == 2000 and c.option_type == 'call':
            print(f"{c.instrument_name}: DTE={c.dte}, IV={c.mark_iv}, Delta={c.delta}, Gamma={c.gamma}")

asyncio.run(main())
