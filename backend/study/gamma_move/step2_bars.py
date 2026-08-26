"""Fetch 15-minute (close, volume, oi) history for the candidate contracts."""
from __future__ import annotations
import asyncio, json, sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study.gamma_move._kite import client, Pacer, candles, norm

OUT = Path(__file__).parent / "out"
LOOKBACK_DAYS = 70


async def main():
    cands = json.loads((OUT / "candidates.json").read_text())["candidates"]
    c = await client()
    pacer = Pacer(rate=2.6)
    to = date.today()
    frm = to - timedelta(days=LOOKBACK_DAYS)
    f, t = frm.strftime("%Y-%m-%d"), to.strftime("%Y-%m-%d")

    store, empty, no_oi = {}, 0, 0
    for i, d in enumerate(cands, 1):
        rows = norm(await candles(c, pacer, d["token"], "15minute", f, t, oi=True))
        if not rows:
            empty += 1
        elif not any((r.get("oi") or 0) > 0 for r in rows):
            no_oi += 1
        else:
            store[d["tradingsymbol"]] = {"meta": d, "bars": rows}
        if i % 20 == 0:
            print(f"  {i}/{len(cands)} … kept={len(store)} empty={empty} no_oi={no_oi}")

    (OUT / "bars.json").write_text(json.dumps(store))
    tot = sum(len(v["bars"]) for v in store.values())
    print(f"contracts with OI bars: {len(store)} | total bars: {tot:,} "
          f"| empty: {empty} | no-oi: {no_oi}")
    if store:
        k = next(iter(store))
        print(f"sample {k}: {len(store[k]['bars'])} bars, first={store[k]['bars'][0]}")

asyncio.run(main())
