"""Pull daily spot for every candidate underlying. Feeds the level (U1) and
SuperTrend (U3) calibrations, and lets the trigger be re-tested *in conjunction*
with R2/R3 rather than on its own."""
from __future__ import annotations
import asyncio, json, sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study.gamma_move._kite import client, Pacer, candles, norm

OUT = Path(__file__).parent / "out"


async def main():
    cands = json.loads((OUT / "candidates.json").read_text())["candidates"]
    names = sorted({d["underlying"] for d in cands})
    c = await client()
    pacer = Pacer(rate=2.6)

    eq = await c.search_instruments("", "NSE", limit=1_000_000)
    tok = {r["tradingsymbol"]: int(r["instrument_token"])
           for r in eq if r.get("segment") == "NSE" and r["tradingsymbol"] in set(names)}
    print(f"resolved {len(tok)}/{len(names)} equity tokens")

    to = date.today(); frm = to - timedelta(days=500)
    f, t = frm.strftime("%Y-%m-%d"), to.strftime("%Y-%m-%d")
    spot = {}
    for i, (n, k) in enumerate(sorted(tok.items()), 1):
        rows = norm(await candles(c, pacer, k, "day", f, t, oi=False))
        if rows:
            spot[n] = rows
        if i % 25 == 0:
            print(f"  {i}/{len(tok)} … kept={len(spot)}")
    (OUT / "spot_daily.json").write_text(json.dumps(spot))
    print(f"daily spot series: {len(spot)} names, "
          f"{sum(len(v) for v in spot.values()):,} bars")

asyncio.run(main())
