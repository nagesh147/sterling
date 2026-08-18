"""Independent F&O universe policy for ORB Momentum Options."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class FNOInstrument:
    symbol: str
    exchange: str
    instrument_type: str
    underlying: str
    has_options: bool = True

def normalize_instrument(row: dict) -> FNOInstrument | None:
    symbol = str(row.get("tradingsymbol") or row.get("symbol") or row.get("name") or "").strip().upper()
    underlying = str(row.get("name") or row.get("underlying") or symbol).strip().upper()
    exchange = str(row.get("exchange") or row.get("segment") or "").upper()
    kind = str(row.get("instrument_type") or row.get("instrument") or "").upper()
    if not symbol or not underlying or exchange not in {"NFO", "NSE", "BSE"}:
        return None
    if kind and kind not in {"EQ", "INDEX", "FUT", "CE", "PE", "OPT"}:
        return None
    return FNOInstrument(symbol, exchange, kind or "EQ", underlying, True)

def build_universe(rows: Iterable[dict], *, excluded: set[str] | None = None) -> list[FNOInstrument]:
    excluded = {x.upper() for x in (excluded or set())}
    result: dict[str, FNOInstrument] = {}
    for row in rows:
        inst = normalize_instrument(row)
        if not inst or inst.underlying in excluded or inst.symbol in excluded:
            continue
        result[inst.underlying] = inst
    return sorted(result.values(), key=lambda x: x.underlying)

def is_option_buy_candidate(symbol: str, option_type: str) -> bool:
    return bool(symbol.strip()) and option_type.upper() in {"CE", "PE"}
