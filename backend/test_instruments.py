import asyncio
from app.services.exchanges.kite.client import KiteClient

async def main():
    client = KiteClient()
    await client.initialize() if hasattr(client, 'initialize') else None
    
    # fetch BFO
    try:
        csv_data = await client._fetch_instruments_csv("BFO")
        lines = csv_data.split('\n')
        headers = lines[0].split(',')
        sensex_rows = []
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) > 5 and parts[3] == "SENSEX":
                sensex_rows.append(parts)
        print("SENSEX count by name:", len(sensex_rows))
        print("Header:", headers)
        if sensex_rows:
            print("First match:", sensex_rows[0])
            
    except Exception as e:
        print("Error fetching BFO:", e)
        
    try:
        from app.services.exchanges.kite.instruments import InstrumentCache
        cache = InstrumentCache(client._fetch_instruments_csv)
        bfo_data = await cache.load("BFO")
        print("Dict keys:", list(bfo_data[0].keys()) if bfo_data else "None")
        matches = [d for d in bfo_data if "SENSEX" in str(d.get("name", "")).upper()]
        print("Cache SENSEX matches by name:", len(matches))
        print("First match:", matches[0] if matches else None)
    except Exception as e:
        print("Error with cache:", e)

if __name__ == "__main__":
    asyncio.run(main())
