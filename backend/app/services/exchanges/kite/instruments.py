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
import concurrent.futures
import csv
import io
import time
from typing import Awaitable, Callable, Dict, List, Optional, Tuple


_MONTHS = {"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"}
_DERIVATIVE_TYPES = {"CE", "PE", "FUT"}


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


async def _parse_instruments_csv_async(text: str) -> List[dict]:
    """Parse off-loop without relying on asyncio's default executor.

    Python 3.14's default-executor shutdown can hang in the local pytest
    environment after `asyncio.to_thread()`. A short-lived executor keeps the
    production non-blocking behavior while giving tests a deterministic
    teardown path.
    """
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="kite-instruments") as executor:
        return await loop.run_in_executor(executor, parse_instruments_csv, text)


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
            if self._fresh(key, now):
                return self._cache[key]
            text = await self._fetch(key)
            rows = await _parse_instruments_csv_async(text)
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

        All whitespace-separated query tokens must appear in the searchable text.
        Ranking is intent-aware: a derivative-specific query containing a month,
        strike, or CE/PE/FUT puts exact derivative matches before the cash-equity
        row. A broad underlying-only query keeps equities/indices above the option
        flood, matching Kite's normal search behaviour.
        """
        q = (query or "").strip().upper()
        rows = await self.load(exchange)
        if not q:
            return rows[:limit]
        tokens = q.split()
        first = tokens[0]
        requested_type = next((tok for tok in tokens if tok in _DERIVATIVE_TYPES), "")
        requested_month = next((tok for tok in tokens if tok in _MONTHS), "")
        requested_strike = next(
            (tok for tok in tokens if tok.replace(".", "", 1).isdigit() and len(tok.split(".", 1)[0]) >= 3),
            "",
        )
        derivative_intent = bool(requested_type or requested_month or requested_strike)
        type_order = {"CE": 0, "PE": 1, "FUT": 2}
        scored = []
        for r in rows:
            ts = str(r.get("tradingsymbol", "")).upper()
            nm = str(r.get("name", "")).upper()
            seg = str(r.get("segment", "")).upper()
            exch = str(r.get("exchange", "")).upper()
            strike_s = self._strike_str(r.get("strike"))
            hay = f"{ts} {nm} {strike_s} {exch} {seg}"
            if all(tok in hay for tok in tokens):
                itype = str(r.get("instrument_type", "")).upper()
                is_derivative = itype in _DERIVATIVE_TYPES
                expiry = str(r.get("expiry") or "9999-99-99")
                try:
                    strike_v = float(r.get("strike") or 0)
                except (TypeError, ValueError):
                    strike_v = 0.0

                # These dimensions are no-ops for broad searches, but for a query
                # such as "BAJAJ-AUTO JUL 10500 CE" they force the exact month,
                # strike and side to the top rather than returning BAJAJ-AUTO EQ.
                type_miss = 0 if not requested_type or itype == requested_type else 1
                month_miss = 0 if not requested_month or requested_month in ts else 1
                strike_miss = 0 if not requested_strike or strike_s == requested_strike else 1
                asset_rank = (
                    0 if is_derivative else 1
                    if derivative_intent
                    else 1 if is_derivative else 0
                )
                rank = (
                    0 if ts == q else 1,
                    type_miss,
                    month_miss,
                    strike_miss,
                    0 if (ts.startswith(first) or nm.startswith(first)) else 1,
                    asset_rank,
                    nm,
                    type_order.get(itype, 9),
                    expiry,
                    strike_v,
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
        """Bulk ``EXCHANGE:TRADINGSYMBOL`` → ``lot_size`` lookup."""
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

    async def expiries(self, symbols: List[str]) -> Dict[str, str]:
        """Bulk ``EXCHANGE:TRADINGSYMBOL`` → ``expiry`` (``YYYY-MM-DD``) lookup."""
        by_ex: Dict[str, List[Tuple[str, str]]] = {}
        for sym in symbols:
            ex, sep, ts = sym.partition(":")
            if not sep:
                ex, ts = "", ex
            by_ex.setdefault(ex.upper(), []).append((sym, ts.upper()))
        out: Dict[str, str] = {}
        for ex, pairs in by_ex.items():
            rows = await self.load(ex)
            idx = {str(r.get("tradingsymbol", "")).upper(): r for r in rows}
            for sym, ts in pairs:
                r = idx.get(ts)
                if r is None:
                    continue
                exp = str(r.get("expiry") or "")[:10]
                if exp:
                    out[sym] = exp
        return out

    def clear(self) -> None:
        self._cache.clear()
        self._cache_ts.clear()
        self._token_cache.clear()
