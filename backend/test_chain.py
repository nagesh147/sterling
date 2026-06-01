import asyncio
from app.api.v1.endpoints.derivatives import _option_chain_or_none
from app.services import adapter_manager as _adm

class MockState:
    adapter = None

class MockApp:
    state = MockState()

async def main():
    import logging
    logging.basicConfig(level=logging.INFO)
    await _adm.initialize()
    chain = await _option_chain_or_none(underlying="ETH", app=MockApp(), spot=3500.0)
    print(f"CHAIN RESULT: {'None' if chain is None else len(chain)}")

asyncio.run(main())
