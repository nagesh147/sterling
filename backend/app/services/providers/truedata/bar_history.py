"""Acquire and canonicalize TrueData 1-minute bars for trial F-101 features."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.replay import CanonicalEventSequence
from app.services.market_data.truedata import TrueDataHistoricalClient, TrueDataNoDataError

from .adapter import TrueDataMarketDataAdapter
from .bar_store import BarStore
from .tick_history import format_history_timestamp, nse_session_chunks


def bars_to_canonical_sequence(
    symbol: str, rows: Sequence[dict]
) -> CanonicalEventSequence:
    events: list[CanonicalMarketEvent] = []
    for index, row in enumerate(rows):
        events.append(
            TrueDataMarketDataAdapter.create_bar_event(symbol, row, sequence=index)
        )
    return CanonicalEventSequence.from_events(events)


@dataclass(frozen=True)
class BarAcquisitionResult:
    symbol: str
    interval: str
    row_count: int
    chunk_count: int
    empty_chunks: int
    dataset_sha256: str


class BarHistoryAcquirer:
    def __init__(
        self,
        client: TrueDataHistoricalClient,
        store: BarStore,
        *,
        min_interval_seconds: float = 0.1,
        interval: str = "1min",
    ) -> None:
        self._client = client
        self._store = store
        self._min_interval = min_interval_seconds
        self._interval = interval

    async def acquire(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> BarAcquisitionResult:
        chunks = nse_session_chunks(start, end)
        if not chunks:
            chunks = [(start, end)]
        last_call = 0.0
        empty_chunks = 0
        for chunk_start, chunk_end in chunks:
            wait = self._min_interval - (asyncio.get_running_loop().time() - last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            request_from = format_history_timestamp(chunk_start)
            request_to = format_history_timestamp(chunk_end)
            try:
                rows = await self._client.get_bars(
                    symbol, request_from, request_to, interval=self._interval
                )
            except TrueDataNoDataError:
                rows = []
                empty_chunks += 1
            last_call = asyncio.get_running_loop().time()
            if rows:
                self._store.upsert(
                    symbol,
                    rows,
                    interval=self._interval,
                    request_from=request_from,
                    request_to=request_to,
                )
        loaded = self._store.load(symbol, interval=self._interval)
        return BarAcquisitionResult(
            symbol=symbol,
            interval=self._interval,
            row_count=len(loaded),
            chunk_count=len(chunks),
            empty_chunks=empty_chunks,
            dataset_sha256=self._store.dataset_sha256(symbol, self._interval),
        )
