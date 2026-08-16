"""Acquire and canonicalize TrueData historical ticks for LiquidityImbalance."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Sequence
from zoneinfo import ZoneInfo

from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.replay import CanonicalEventSequence
from app.services.market_data.truedata import TrueDataHistoricalClient

from .adapter import TrueDataMarketDataAdapter
from .tick_store import TickStore

IST = ZoneInfo("Asia/Kolkata")
SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)


def format_history_timestamp(dt: datetime) -> str:
    """TrueData v2.6 /getticks from/to: yymmddTHH:mm:ss in the provider session clock."""
    return dt.astimezone(IST).strftime("%y%m%dT%H:%M:%S")


def nse_session_chunks(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    start_local = start.astimezone(IST)
    end_local = end.astimezone(IST)
    chunks: list[tuple[datetime, datetime]] = []
    day = start_local.date()
    last = end_local.date()
    while day <= last:
        open_dt = datetime.combine(day, SESSION_OPEN, tzinfo=IST)
        close_dt = datetime.combine(day, SESSION_CLOSE, tzinfo=IST)
        chunk_start = max(open_dt, start_local)
        chunk_end = min(close_dt, end_local)
        if chunk_start < chunk_end and day.weekday() < 5:
            chunks.append((chunk_start, chunk_end))
        day += timedelta(days=1)
    return chunks


def ticks_to_canonical_sequence(
    symbol: str, rows: Sequence[dict]
) -> CanonicalEventSequence:
    events: list[CanonicalMarketEvent] = []
    for row in rows:
        ordinal = int(row.get("row_ordinal") or 0)
        events.append(
            TrueDataMarketDataAdapter.create_tick_event(symbol, row, sequence=ordinal)
        )
    return CanonicalEventSequence.from_events(events)


@dataclass(frozen=True)
class TickAcquisitionResult:
    symbol: str
    row_count: int
    chunk_count: int
    dataset_sha256: str


class TickHistoryAcquirer:
    def __init__(
        self,
        client: TrueDataHistoricalClient,
        store: TickStore,
        *,
        min_interval_seconds: float | None = None,
    ) -> None:
        documented = 1.0 / max(client.TICK_PER_SECOND, 1)
        self._client = client
        self._store = store
        self._min_interval = documented if min_interval_seconds is None else min_interval_seconds

    async def acquire(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        *,
        bidask: int = 1,
    ) -> TickAcquisitionResult:
        chunks = nse_session_chunks(start, end)
        if not chunks:
            chunks = [(start.astimezone(IST), end.astimezone(IST))]
        last_call = 0.0
        for chunk_start, chunk_end in chunks:
            wait = self._min_interval - (asyncio.get_running_loop().time() - last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            request_from = format_history_timestamp(chunk_start)
            request_to = format_history_timestamp(chunk_end)
            rows = await self._client.get_ticks(
                symbol, request_from, request_to, bidask=bidask
            )
            last_call = asyncio.get_running_loop().time()
            self._store.upsert(
                symbol, rows, request_from=request_from, request_to=request_to
            )
        loaded = self._store.load(symbol)
        return TickAcquisitionResult(
            symbol=symbol,
            row_count=len(loaded),
            chunk_count=len(chunks),
            dataset_sha256=self._store.dataset_sha256(symbol),
        )

    async def acquire_symbols(
        self,
        symbols: Sequence[str],
        start: datetime,
        end: datetime,
        *,
        bidask: int = 1,
    ) -> dict[str, TickAcquisitionResult]:
        """Acquire tick history for multiple symbols in sequence respecting rate limits."""
        results: dict[str, TickAcquisitionResult] = {}
        for symbol in symbols:
            results[symbol] = await self.acquire(symbol, start, end, bidask=bidask)
        return results
