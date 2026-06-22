"""Diagnostic: trace the EXACT Kite-engine derivative resolution path end-to-end.

Read-only (instruments / historical / quote — NO orders). Prints what happens at
every boundary so we can see WHERE derivative signals are lost.
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta

from app.services import db
from app.services.exchanges.kite import accounts
from app.services.kite_engine.universe import build_universe, select_scan_universe
from app.services.kite_engine.strikes import chain_rows_for, pick_contracts
from app.services.kite_engine.scanner import (
    scanner, drop_forming, evaluate_derivative_contract,
)
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.schemas import EngineConfigModel

_IST = timezone(timedelta(hours=5, minutes=30))


def P(*a):
    print(*a, flush=True)


async def main():
    accts = [a for a in accounts._load_from_db() if a.connected]
    P(f"connected accounts: {len(accts)}")
    if not accts:
        P("NO CONNECTED ACCOUNT — cannot trace live. (token likely expired)")
        return
    acct = accts[0]
    uid = acct.user_id
    client = accounts.build_client(acct)

    # 0) saved config
    saved = None
    try:
        raw = db.get_config(f"kite_engine_config_{uid}")
        saved = EngineConfigModel.model_validate_json(raw) if raw else EngineConfigModel()
    except Exception as e:
        P("config load err:", e); saved = EngineConfigModel()
    P("\n=== SAVED CONFIG ===")
    P("scan_source     :", saved.scan_source)
    P("strike_moneyness:", saved.strike_moneyness)
    P("scan_indices    :", saved.scan_indices)
    P("scan_all_stocks :", saved.scan_all_stocks)
    moneyness = saved.strike_moneyness
    cfg = SterlingKiteEngineConfig(trail_target=saved.trail_target)
    P("warmup bars     :", cfg.warmup)

    try:
        prof = await client.get_profile()
        P("\nprofile OK:", (prof or {}).get("user_id"))
    except Exception as e:
        P("\nPROFILE FAILED (token expired?):", e)
        await client.close(); return

    # 1) instruments + universe
    nfo = await client.search_instruments("", "NFO", limit=1_000_000)
    bfo = await client.search_instruments("", "BFO", limit=1_000_000)
    nse = await client.search_instruments("", "NSE", limit=1_000_000)
    bse = await client.search_instruments("", "BSE", limit=1_000_000)
    P(f"\ninstruments: NFO={len(nfo)} BFO={len(bfo)} NSE={len(nse)} BSE={len(bse)}")

    # what does a SENSEX option row actually look like? (name field == ?)
    sx = [r for r in bfo if str(r.get("name", "")).upper() in ("SENSEX", "BSX")
          and r.get("instrument_type") in ("CE", "PE")][:3]
    P("sample BFO SENSEX/BSX rows:")
    for r in sx:
        P("   name=%r tsym=%r type=%r strike=%r expiry=%r token=%r" % (
            r.get("name"), r.get("tradingsymbol"), r.get("instrument_type"),
            r.get("strike"), str(r.get("expiry"))[:10], r.get("instrument_token")))
    name_field_vals = sorted({str(r.get("name")) for r in bfo
                              if "SENSEX" in str(r.get("tradingsymbol", "")).upper()})[:5]
    P("distinct BFO `name` where tradingsymbol~SENSEX:", name_field_vals)

    full = build_universe(nfo_instruments=nfo, bfo_instruments=bfo, equities=nse + bse)
    idx = {u.name: u for u in full if u.is_index}
    P("\nuniverse indices:", list(idx.keys()))
    for nm in ("SENSEX", "NIFTY 50", "NIFTY BANK"):
        u = idx.get(nm)
        P(f"   {nm}: token={u.token} tsym={u.tradingsymbol} opt_exch={u.option_exchange}" if u else f"   {nm}: MISSING")

    selected = select_scan_universe(full, indices=saved.scan_indices,
                                    stocks=saved.scan_stocks, all_stocks=saved.scan_all_stocks)
    P("selected universe size:", len(selected), "indices:", [u.name for u in selected if u.is_index])

    today = datetime.now(_IST).date()

    # 2) per-index derivative trace (SENSEX + NIFTY 50)
    for nm in ("SENSEX", "NIFTY 50"):
        u = idx.get(nm)
        if not u:
            P(f"\n### {nm}: not in universe"); continue
        P(f"\n################ {nm} (token={u.token}, tsym={u.tradingsymbol}, opt_exch={u.option_exchange}) ################")

        # 2a) underlying 1H candles via token
        from app.schemas.instruments import InstrumentMeta
        inst = InstrumentMeta(underlying=u.tradingsymbol, tick_size=0.05, strike_step=1.0,
                              exchange_currency="INR", perp_symbol="", index_name=u.name,
                              has_options=True, exchange="zerodha", zerodha_token=u.token)
        try:
            cand = drop_forming(await client.get_candles(inst, "1H", 320))
        except Exception as e:
            cand = []; P("  underlying candle fetch EXC:", e)
        P(f"  [2a] underlying 1H candles via token {u.token}: {len(cand)} bars" +
          (f" (last close={cand[-1].close})" if cand else "  <-- EMPTY (silent drop)"))

        spot = float(cand[-1].close) if cand else 0.0

        # 2b) quote fallback (production: f'BSE:{tsym}' / f'NSE:{tsym}')
        qsym = f"BSE:{u.tradingsymbol}" if u.option_exchange == "BFO" else f"NSE:{u.tradingsymbol}"
        try:
            q = await client.get_quote([qsym])
            lp = float((q.get(qsym) or {}).get("last_price") or 0.0) if q else 0.0
            P(f"  [2b] PROD fallback quote {qsym!r} -> last_price={lp}" + ("  <-- FAILED" if lp <= 0 else ""))
        except Exception as e:
            P(f"  [2b] PROD fallback quote {qsym!r} EXC: {e}")
        # also try the display-name quote (the proposed fix)
        qsym2 = f"BSE:{u.name}" if u.option_exchange == "BFO" else f"NSE:{u.name}"
        if qsym2 != qsym:
            try:
                q2 = await client.get_quote([qsym2])
                lp2 = float((q2.get(qsym2) or {}).get("last_price") or 0.0) if q2 else 0.0
                P(f"  [2b'] display-name quote {qsym2!r} -> last_price={lp2}" + ("  <-- works (fix)" if lp2 > 0 else ""))
            except Exception as e:
                P(f"  [2b'] display-name quote {qsym2!r} EXC: {e}")

        if spot <= 0:
            P("  spot<=0 after candles; production would use the fallback quote above")

        # 2c) chain resolution
        opt_rows = nfo if u.option_exchange == "NFO" else bfo
        chain = chain_rows_for(opt_rows, u.tradingsymbol, today)
        P(f"  [2c] chain_rows_for({u.tradingsymbol!r}): {len(chain)} option rows")
        if chain:
            dtes = sorted({c['dte'] for c in chain})
            P(f"       distinct DTEs: {dtes[:8]}  nearest expiry rows: {sum(1 for c in chain if c['dte']==min(d for d in dtes if d>=1))}")

        use_spot = spot if spot > 0 else 76264.0  # fallback for trace if needed
        # 2d) pick contracts at saved moneyness
        contracts = pick_contracts(chain, spot=use_spot, moneynesses=moneyness)
        P(f"  [2d] pick_contracts(spot={use_spot}, moneyness={list(moneyness)}): {len(contracts)} contracts")
        for m, pk in contracts:
            P(f"        {m:5} {pk.option_type} {pk.option_symbol} strike={pk.strike} dte={pk.dte} token={pk.token}")

        # 2e) per-contract premium candle fetch + evaluate
        for m, pk in contracts:
            try:
                inst2 = InstrumentMeta(underlying=pk.option_symbol, tick_size=0.05, strike_step=1.0,
                                       exchange_currency="INR", perp_symbol="", index_name=pk.option_symbol,
                                       has_options=True, exchange="zerodha", zerodha_token=pk.token)
                oc = drop_forming(await client.get_candles(inst2, "1H", 320))
            except Exception as e:
                oc = []; P(f"  [2e] {m} {pk.option_symbol} candle EXC: {e}")
            sig = evaluate_derivative_contract(u, m, pk, oc, cfg) if oc else []
            ts = [datetime.fromtimestamp(s.timestamp_ms/1000, _IST).strftime("%m-%d %H:%M") for s in sig]
            P(f"  [2e] {m:5} {pk.option_symbol}: premium bars={len(oc)} warmup={cfg.warmup} -> {len(sig)} long-signals {ts}")

    await client.close()
    P("\n=== DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
