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

import asyncio
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
        self._locks: Dict[str, asyncio.Lock] = {}

    def _fresh(self, key: str, now: float) -> bool:
        return key in self._cache and (now - self._cache_ts.get(key, 0.0)) < self._ttl

    async def load(self, exchange: str = "") -> List[dict]:
        """Return cached rows for ``exchange`` (``""`` = full dump), fetching if stale.

        A per-key lock dedupes concurrent cold loads (the client is now shared, so
        a burst of searches/scans must not each download the multi-MB dump), and
        the ~80k-row CSV parse runs in a thread so it never blocks the event loop.
        """
        key = (exchange or "").upper()
        now = time.monotonic()
        if self._fresh(key, now):
            return self._cache[key]
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            if self._fresh(key, now):           # filled while we waited for the lock
                return self._cache[key]
            text = await self._fetch(key)
            rows = await asyncio.to_thread(parse_instruments_csv, text)
            self._cache[key] = rows
            self._cache_ts[key] = now
            return rows

    @staticmethod
    def _strike_str(strike) -> str:
        try:
            f = float(strike)
        except (TypeError, ValueError):
            return ""
        if f <= 0:
            return ""
        return str(int(f)) if f.is_integer() else str(f)

    async def search(self, query: str, exchange: str = "", limit: int = 50) -> List[dict]:
        """Kite-style universal instrument search.

        ``exchange=""`` searches the full dump (all segments — equities, futures,
        options, indices, currencies, commodities). The query is whitespace-tokenized
        and ALL tokens must appear in the instrument's searchable text
        (tradingsymbol + name + strike + exchange + segment), so
        ``"nifty 24000 ce"`` matches ``NFO:NIFTY24D2624000CE``. Results are ranked:
        exact tradingsymbol → prefix match → shorter symbol (equities/indices float
        above the option flood) → alphabetical.
        """
        q = (query or "").strip().upper()
        rows = await self.load(exchange)
        if not q:
            return rows[:limit]
        tokens = q.split()
        first = tokens[0]
        scored = []
        for r in rows:
            ts = str(r.get("tradingsymbol", "")).upper()
            nm = str(r.get("name", "")).upper()
            seg = str(r.get("segment", "")).upper()
            exch = str(r.get("exchange", "")).upper()
            hay = f"{ts} {nm} {self._strike_str(r.get('strike'))} {exch} {seg}"
            if all(tok in hay for tok in tokens):
                rank = (
                    0 if ts == q else 1,
                    0 if (ts.startswith(first) or nm.startswith(first)) else 1,
                    len(ts),
                    ts,
                )
                scored.append((rank, r))
        scored.sort(key=lambda x: x[0])
        return [r for _, r in scored[:limit]]

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

    async def lot_sizes(self, symbols: List[str]) -> Dict[str, int]:
        """Bulk ``EXCHANGE:TRADINGSYMBOL`` → ``lot_size`` lookup.

        Only instruments actually found are returned (callers keep their own
        fallback for anything unresolved). Each exchange dump is loaded at most
        once, then resolved in-memory — cheap for a whole watchlist.
        """
        by_ex: Dict[str, List[Tuple[str, str]]] = {}
        for sym in symbols:
            ex, sep, ts = sym.partition(":")
            if not sep:
                ex, ts = "", ex
            by_ex.setdefault(ex.upper(), []).append((sym, ts.upper()))
        out: Dict[str, int] = {}
        for ex, pairs in by_ex.items():
            rows = await self.load(ex)
            idx = {str(r.get("tradingsymbol", "")).upper(): r for r in rows}
            for sym, ts in pairs:
                r = idx.get(ts)
                if r is None:
                    continue
                ls = int(r.get("lot_size") or 0)
                out[sym] = ls if ls > 0 else 1
        return out

    def clear(self) -> None:
        self._cache.clear()
        self._cache_ts.clear()
        self._token_cache.clear()
