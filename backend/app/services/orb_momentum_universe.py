"""F&O universe policy for ORB Momentum Options.

The strategy scans eligible Indian F&O underlyings only. Option contracts are
execution candidates; signals are generated from the underlying.
"""
from __future__ import annotations
from dataclasses import dataclass
from app.services.exchanges import instrument_registry as registry

@dataclass(frozen=True)
class ORBUniverse:
    symbols: tuple[str, ...]
    indices: tuple[str, ...]
    stocks: tuple[str, ...]


def build_universe(extra_symbols: list[str] | None = None, excluded: list[str] | None = None) -> ORBUniverse:
    excluded_set = {x.upper() for x in (excluded or [])}
    extras = {x.upper() for x in (extra_symbols or [])}
    configured = {i.underlying.upper() for i in registry.list_instruments() if i.has_options and i.exchange == "zerodha"}
    configured |= extras
    configured -= excluded_set
    indices = tuple(x for x in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY") if x in configured)
    stocks = tuple(sorted(configured - set(indices)))
    return ORBUniverse(tuple(indices + stocks), indices, stocks)


def is_fno_symbol(symbol: str, universe: ORBUniverse | None = None) -> bool:
    u = universe or build_universe()
    return symbol.upper() in u.symbols
