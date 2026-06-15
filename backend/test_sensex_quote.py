import asyncio
from app.services.exchanges.kite.client import KiteClient
from app.core.config import settings

async def main():
    client = KiteClient()
    await client.initialize()
    q = await client.get_quote(["BSE:SENSEX"])
    print(q)
    
if __name__ == "__main__":
    asyncio.run(main())
