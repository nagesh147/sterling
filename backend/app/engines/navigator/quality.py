"""Closed-candle validation for the Navigator price feature engine (spec §7.1).

Every price-feature module (`avwap.py`, `projected_ranges.py`,
`volatility.py`) takes its input through `validate_candles` first — never
raw broker candles. Reuses the existing `app.schemas.market.Candle` shape
rather than inventing a parallel one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence
from zoneinfo import ZoneInfo

import numpy as np
from numpy.typing import NDArray

from app.schemas.market import Candle

IST = ZoneInfo("Asia/Kolkata")


class CandleValidationError(ValueError):
    """Raised when the input candle series is malformed. Callers must treat
    this as `PRICE_BARS_MISSING`/`PRICE_VOLUME_INVALID` evidence — never
    attempt to repair or silently drop invalid bars mid-series."""


@dataclass(frozen=True)
class ValidatedCandles:
    """Column-oriented, guaranteed-clean candle arrays: strictly timestamp-
    ascending, no duplicates, finite, non-negative, OHLC-consistent."""

    timestamp_ms: NDArray[np.int64]
    open: NDArray[np.float64]
    high: NDArray[np.float64]
    low: NDArray[np.float64]
    close: NDArray[np.float64]
    volume: NDArray[np.float64]

    @property
    def n(self) -> int:
        return len(self.timestamp_ms)

    def typical_price(self) -> NDArray[np.float64]:
        return (self.high + self.low + self.close) / 3.0


def validate_candles(candles: Sequence[Candle]) -> ValidatedCandles:
    if not candles:
        raise CandleValidationError("no candles supplied")

    ts = np.array([c.timestamp_ms for c in candles], dtype=np.int64)
    o = np.array([c.open for c in candles], dtype=np.float64)
    h = np.array([c.high for c in candles], dtype=np.float64)
    l = np.array([c.low for c in candles], dtype=np.float64)
    cl = np.array([c.close for c in candles], dtype=np.float64)
    v = np.array([c.volume for c in candles], dtype=np.float64)

    for name, arr in (("open", o), ("high", h), ("low", l), ("close", cl), ("volume", v)):
        if not np.all(np.isfinite(arr)):
            raise CandleValidationError(f"non-finite value present in {name!r}")

    if np.any(o < 0) or np.any(h < 0) or np.any(l < 0) or np.any(cl < 0):
        raise CandleValidationError("negative price present")
    if np.any(v < 0):
        raise CandleValidationError("negative volume present")
    if np.any(h < np.maximum(o, cl)):
        raise CandleValidationError("high < max(open, close) on at least one bar")
    if np.any(l > np.minimum(o, cl)):
        raise CandleValidationError("low > min(open, close) on at least one bar")
    if ts.size > 1 and np.any(np.diff(ts) <= 0):
        raise CandleValidationError(
            "candles must be strictly ascending by timestamp_ms with no duplicates"
        )

    return ValidatedCandles(timestamp_ms=ts, open=o, high=h, low=l, close=cl, volume=v)


def ist_calendar_dates(timestamp_ms: NDArray[np.int64]) -> list[date]:
    """IST calendar date for each bar close timestamp. Shared by every
    Navigator module that needs session/day boundaries (AVWAP session VWAP,
    projected daily/weekly ranges) — a change of IST date between
    consecutive bars IS a new session boundary, with no separate holiday
    calendar needed since the input series only contains bars for sessions
    the exchange actually traded."""
    return [datetime.fromtimestamp(ts / 1000.0, tz=IST).date() for ts in timestamp_ms]
