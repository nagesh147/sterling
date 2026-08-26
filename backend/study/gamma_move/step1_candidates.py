"""Pick the contracts a Gamma Move scan would actually watch, then keep them.

R4 says: the highest-open-interest strike near the level. So the calibration
sample must be highest-OI strikes on liquid names -- not a random slice of the
chain, whose volume and OI distributions look nothing like the traded one.
"""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study.gamma_move._kite import client, Pacer

INDEX = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}
OUT = Path(__file__).parent / "out"; OUT.mkdir(exist_ok=True)
TOP_NAMES = 110
TOP_STRIKES_PER_LEG = 3
STRIKE_BAND_PCT = 8.0
#: Below this the tick size dominates the premium -- a 0.05 tick on a 0.73 option
#: is a 7% quantum, so `price_gain_pct` would be measuring tick granularity, not
#: a gamma move. The source's own examples enter at 75, 540 and 600.
MIN_PREMIUM = 10.0


async def quote_batched(c, pacer, keys, size=200):
    out = {}
    for i in range(0, len(keys), size):
        for attempt in range(4):
            await pacer.wait()
            try:
                out.update(await c.get_quote(keys[i:i + size]) or {})
                break
            except Exception as exc:                               # noqa: BLE001
                if attempt == 3:
                    print(f"   quote batch {i} gave up: {exc}", file=sys.stderr)
                else:
                    await asyncio.sleep(1.5 * (attempt + 1))
    return out


async def main():
    c = await client()
    pacer = Pacer(rate=0.7)                    # /quote is the 1 rq/s endpoint; stay under
    rows = await c.search_instruments("", "NFO", limit=1_000_000)

    fut = [r for r in rows if r.get("segment") == "NFO-FUT" and r["name"] not in INDEX]
    near_fut_exp = sorted({r["expiry"] for r in fut})[0]
    fut = [r for r in fut if r["expiry"] == near_fut_exp]
    print(f"near-month stock futures: {len(fut)} @ {near_fut_exp}")

    # Rank liquidity by futures OI: one quote call ranks the whole universe,
    # where ranking by option OI would need to quote the entire chain first.
    fq = await quote_batched(c, pacer, [f"NFO:{r['tradingsymbol']}" for r in fut])
    # Rank by NOTIONAL open interest, not share count. IDEA carries 400m shares
    # of OI because the share is Rs 15 -- ranking on the raw count fills the
    # sample with sub-rupee options whose tick size is a 7% price quantum.
    liq = []
    for r in fut:
        q = fq.get(f"NFO:{r['tradingsymbol']}") or {}
        oi, px = float(q.get("oi") or 0), float(q.get("last_price") or 0)
        liq.append((oi * px, oi, r["name"]))
    liq.sort(reverse=True)
    names = [n for _, _, n in liq[:TOP_NAMES]]
    print(f"top {len(names)} by futures OI notional: {', '.join(names[:12])} …")

    spot = await quote_batched(c, pacer, [f"NSE:{n}" for n in names])
    ltp = {n: float((spot.get(f"NSE:{n}") or {}).get("last_price") or 0) for n in names}
    names = [n for n in names if ltp[n] > 0]

    opt = [r for r in rows if r.get("segment") == "NFO-OPT" and r["name"] in set(names)]
    near_exp = sorted({r["expiry"] for r in opt})[0]
    opt = [r for r in opt if r["expiry"] == near_exp]
    band = [r for r in opt
            if abs(float(r["strike"]) - ltp[r["name"]]) / ltp[r["name"]] * 100 <= STRIKE_BAND_PCT]
    print(f"expiry {near_exp}: {len(band)} strikes within ±{STRIKE_BAND_PCT}% of spot")

    oq = await quote_batched(c, pacer, [f"NFO:{r['tradingsymbol']}" for r in band])

    # The top strikes by OI per (name, leg) -- R4's pick, plus the runners-up it
    # would have taken on a different day, which is what makes the calibration
    # sample big enough to be worth trusting.
    pool: dict[tuple[str, str], list] = {}
    for r in band:
        q = oq.get(f"NFO:{r['tradingsymbol']}") or {}
        oi, px = float(q.get("oi") or 0), float(q.get("last_price") or 0)
        if oi <= 0 or px < MIN_PREMIUM:
            continue
        pool.setdefault((r["name"], r["instrument_type"]), []).append({
                "underlying": r["name"], "tradingsymbol": r["tradingsymbol"],
                "token": int(r["instrument_token"]), "option_type": r["instrument_type"],
                "strike": float(r["strike"]), "expiry": r["expiry"],
                "lot_size": int(r["lot_size"]), "tick_size": float(r["tick_size"]),
                "oi": oi, "volume": int(q.get("volume") or 0),
                "ltp": float(q.get("last_price") or 0), "spot": ltp[r["name"]],
                "strike_distance_pct": round(
                    (float(r["strike"]) - ltp[r["name"]]) / ltp[r["name"]] * 100, 3),
            })
    cands = [d for legs in pool.values()
             for d in sorted(legs, key=lambda x: -x["oi"])[:TOP_STRIKES_PER_LEG]]
    cands.sort(key=lambda d: -d["oi"])
    (OUT / "candidates.json").write_text(json.dumps(
        {"expiry": near_exp, "spot": ltp, "candidates": cands}, indent=1))
    print(f"kept {len(cands)} contracts ({len({d['underlying'] for d in cands})} names)")
    for d in cands[:8]:
        print(f"   {d['tradingsymbol']:<22} OI={d['oi']:>12,.0f} vol={d['volume']:>10,} "
              f"ltp={d['ltp']:>8.2f} spot={d['spot']:>9.2f} d={d['strike_distance_pct']:+.1f}%")

asyncio.run(main())
