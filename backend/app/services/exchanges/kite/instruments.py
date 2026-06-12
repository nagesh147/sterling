"""
Kite instruments cache + search + symbol↔token resolution.

The full instrument dump (``/instruments``) is ~1.5 MB / ~80k rows, so it is
fetched lazily, scoped per-exchange (NSE/NFO/MCX/…), and cached with a TTL. The
full dump is only pulled when an exchange isn't specified.

``InstrumentCache`` is fed an async ``fetch_csv(exchange) -> str`` callable by the
owning :class:`KiteClient`, keeping this module free of HTTP concerns and unit
testable with a fake fetcher.
"""
from __future__ import annotations

import csv
import io
import time
from typing import Awaitable, Callable, Dict, List, Optional, Tuple


def parse_instruments_csv(text: str) -> List[dict]:
    """Parse a Kite instruments CSV dump into a list of row dicts.

    Numeric columns (instrument_token, exchange_token, strike, lot_size,
    tick_size) are coerced; everything else is left as text.
    """
    rows: List[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        for int_col in ("instrument_token", "exchange_token", "lot_size"):
            if row.get(int_col):
                try:
                    row[int_col] = int(float(row[int_col]))
                except (TypeError, ValueError):
                    pass
        for float_col in ("strike", "tick_size", "last_price"):
            if row.get(float_col):
                try:
                    row[float_col] = float(row[float_col])
                except (TypeError, ValueError):
                    pass
        rows.append(row)
    return rows


class InstrumentCache:
    def __init__(
        self,
        fetch_csv: Callable[[str], Awaitable[str]],
        ttl: float = 3600.0,
    ) -> None:
        self._fetch = fetch_csv
        self._ttl = ttl
        self._cache: Dict[str, List[dict]] = {}
        self._cache_ts: Dict[str, float] = {}
        self._token_cache: Dict[Tuple[str, str], int] = {}

    async def load(self, exchange: str = "") -> List[dict]:
        """Return cached rows for ``exchange`` (``""`` = full dump), fetching if stale."""
        key = (exchange or "").upper()
        now = time.monotonic()
        if key in self._cache and (now - self._cache_ts.get(key, 0.0)) < self._ttl:
            return self._cache[key]
        text = await self._fetch(key)
        rows = parse_instruments_csv(text)
        self._cache[key] = rows
        self._cache_ts[key] = now
        return rows

    async def search(self, query: str, exchange: str = "NFO", limit: int = 50) -> List[dict]:
        """Case-insensitive substring match on tradingsymbol / name."""
        q = (query or "").strip().upper()
        rows = await self.load(exchange)
        if not q:
            return rows[:limit]
        out: List[dict] = []
        for r in rows:
            ts = str(r.get("tradingsymbol", "")).upper()
            nm = str(r.get("name", "")).upper()
            if q in ts or q in nm:
                out.append(r)
                if len(out) >= limit:
                    break
        return out

    async def resolve_token(self, tradingsymbol: str, exchange: str = "NFO") -> int:
        """Exact tradingsymbol → instrument_token (int). Raises if not found."""
        ex = (exchange or "").upper()
        ts = (tradingsymbol or "").upper()
        cached = self._token_cache.get((ex, ts))
        if cached is not None:
            return cached
        rows = await self.load(ex)
        for r in rows:
            if str(r.get("tradingsymbol", "")).upper() == ts:
                tok = int(r.get("instrument_token") or 0)
                self._token_cache[(ex, ts)] = tok
                return tok
        raise KeyError(f"Instrument not found: {exchange}:{tradingsymbol}")

    def clear(self) -> None:
        self._cache.clear()
        self._cache_ts.clear()
        self._token_cache.clear()
