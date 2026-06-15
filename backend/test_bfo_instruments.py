import asyncio
from app.services.exchanges.kite import accounts
from app.services.exchanges.kite.client import KiteClient

async def main():
    acct = accounts.list_accounts()[0]
    client = accounts.build_client(acct)
    bfo = await client.search_instruments("", "BFO", limit=1_000_000)
    for row in bfo:
        if "SENSEX" in str(row.get("tradingsymbol", "")):
            print(row.get("name"), row.get("tradingsymbol"))
            break
    await client.close()

asyncio.run(main())
