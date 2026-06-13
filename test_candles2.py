from app.services.exchanges import instrument_registry as registry

sym = "NSE:NIFTY 50"
inst = registry.get_instrument(sym)
if not inst:
    for candidate in registry.list_instruments():
        if getattr(candidate, "zerodha_index_symbol", None) == sym:
            inst = candidate
            break

print("Found inst:", inst.underlying if inst else "None")
