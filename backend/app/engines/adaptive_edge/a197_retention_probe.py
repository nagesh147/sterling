"""Deterministic, read-only TrueData retention probe for A197."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from typing import Awaitable, Callable, Sequence
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
OPEN = time(9, 15)
CLOSE = time(9, 16)


@dataclass(frozen=True)
class RetentionProbeObservation:
    session_date: date
    row_count: int
    error: str | None = None


@dataclass(frozen=True)
class RetentionProbeReport:
    symbol: str
    requested_start: date
    requested_end: date
    observations: tuple[RetentionProbeObservation, ...]

    @property
    def successful_days(self) -> tuple[date, ...]:
        return tuple(o.session_date for o in self.observations if o.row_count > 0 and o.error is None)

    @property
    def empty_days(self) -> tuple[date, ...]:
        return tuple(o.session_date for o in self.observations if o.row_count == 0 and o.error is None)

    @property
    def error_days(self) -> tuple[date, ...]:
        return tuple(o.session_date for o in self.observations if o.error is not None)

    @property
    def observed_trading_days(self) -> int:
        return len(self.successful_days)

    @property
    def status(self) -> str:
        if self.error_days:
            return "A197_RETENTION_PROBE_INCONCLUSIVE"
        if self.observed_trading_days == 0:
            return "A197_NO_HISTORICAL_TICK_EVIDENCE"
        return "A197_HISTORICAL_TICK_EVIDENCE_FOUND"


async def probe_retention(
    symbol: str,
    start: date,
    end: date,
    fetch_window: Callable[[str, str, str], Awaitable[Sequence[dict]]],
) -> RetentionProbeReport:
    """Probe one-minute opening windows on weekdays without mutating data."""
    if end < start:
        raise ValueError("probe end date cannot precede start date")
    observations: list[RetentionProbeObservation] = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            begin = datetime.combine(day, OPEN, tzinfo=IST).strftime("%y%m%dT%H:%M:%S")
            finish = datetime.combine(day, CLOSE, tzinfo=IST).strftime("%y%m%dT%H:%M:%S")
            try:
                rows = await fetch_window(symbol, begin, finish)
                observations.append(RetentionProbeObservation(day, len(rows)))
            except Exception as exc:
                observations.append(RetentionProbeObservation(day, 0, type(exc).__name__))
        day += timedelta(days=1)
    return RetentionProbeReport(symbol, start, end, tuple(observations))
