"""Kite candles and ticks to CanonicalMarketEvent.

The strategy pipeline consumes canonical events, and until now only TrueData
could produce them — which is the structural reason the pipeline was never wired
to the running engine. This is the missing side.

The load-bearing decision here is `available_at`.

A Kite historical candle is timestamped at the bar's **start**. Its close is not
knowable until the bar ends, so an event whose `available_at` is the bar's own
timestamp claims the close was available a full interval before it existed. The
pipeline orders and gates everything on `available_at`, so that single choice is
the difference between a causal backtest and one that trades on information it
could not have had.

So: `event_time` is the bar's start and `available_at` is its close. Nothing here
is available at its own open.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from .event_boundary import CanonicalEventBoundary, CanonicalMarketEvent

SOURCE_NAME = "kite"
SOURCE_VERSION = "3"

#: Kite's interval vocabulary, in seconds. Used to derive a bar's close from its
#: start; an unknown interval is an error rather than a guess, because guessing
#: short would republish the lookahead this module exists to prevent.
INTERVAL_SECONDS: dict[str, int] = {
    "minute": 60,
    "3minute": 180,
    "5minute": 300,
    "10minute": 600,
    "15minute": 900,
    "30minute": 1800,
    "60minute": 3600,
    "day": 86_400,
}


def interval_seconds(interval: str) -> int:
    try:
        return INTERVAL_SECONDS[str(interval)]
    except KeyError:
        raise ValueError(
            f"unknown Kite interval {interval!r}; add it to INTERVAL_SECONDS rather "
            f"than defaulting, because a too-short interval makes a bar look "
            f"available before it closed"
        ) from None


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _record_id(prefix: str, symbol: str, stamp: str, ordinal: int = 0) -> str:
    digest = hashlib.sha256(f"{symbol}|{stamp}|{ordinal}".encode()).hexdigest()[:12]
    return f"KITE-{prefix}-{symbol}-{digest}"


def bar_event(
    symbol: str,
    candle: Mapping[str, Any],
    *,
    interval: str = "minute",
    sequence: int | None = None,
) -> CanonicalMarketEvent:
    """One Kite candle as a canonical bar event.

    Accepts either a `Candle` model dumped to a mapping or a raw Kite row, so a
    caller does not have to normalize twice.
    """
    raw_ms = candle.get("timestamp_ms")
    if raw_ms is None:
        stamp = candle.get("date") or candle.get("timestamp")
        if stamp is None:
            raise ValueError("candle has no timestamp")
        parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        opened = parsed
    else:
        opened = datetime.fromtimestamp(int(raw_ms) / 1000.0, tz=timezone.utc)

    closed = opened + timedelta(seconds=interval_seconds(interval))
    event_time = opened.isoformat()
    available_at = closed.isoformat()

    close = _num(candle.get("close"))
    return CanonicalEventBoundary.create(
        record_id=_record_id("BAR", symbol, event_time),
        event_type="bar",
        instrument_id=symbol,
        event_time=event_time,
        # The bar's close, not its open. See the module docstring.
        available_at=available_at,
        source=SOURCE_NAME,
        source_version=SOURCE_VERSION,
        payload={
            "open": _num(candle.get("open"), close),
            "high": _num(candle.get("high"), close),
            "low": _num(candle.get("low"), close),
            "close": close,
            "volume": _num(candle.get("volume")),
            "oi": _num(candle.get("oi")),
        },
        source_timestamp=event_time,
        sequence=sequence,
        provenance={
            "provider": "Kite",
            "feed_type": "historical_bar",
            "interval": str(interval),
        },
    )


def bar_events(
    symbol: str,
    candles: Sequence[Mapping[str, Any]],
    *,
    interval: str = "minute",
) -> list[CanonicalMarketEvent]:
    """A whole series, ordered and de-duplicated by record identity.

    Sorted by the time each bar became available rather than by the order the
    provider happened to return them, because that is the order the pipeline
    folds them in.
    """
    seen: set[str] = set()
    out: list[CanonicalMarketEvent] = []
    for index, candle in enumerate(candles or ()):
        try:
            event = bar_event(symbol, candle, interval=interval, sequence=index)
        except (ValueError, TypeError):
            # One malformed row must not discard the series; the pipeline reports
            # what it received, and a gap is visible in the bar count.
            continue
        if event.record_id in seen:
            continue
        seen.add(event.record_id)
        out.append(event)
    out.sort(key=lambda e: (e.available_at, e.record_id))
    return out


def tick_event(
    symbol: str,
    tick: Mapping[str, Any],
    *,
    sequence: int = 0,
) -> CanonicalMarketEvent:
    """One Kite tick as a canonical tick event.

    A tick is available when it is observed, so `available_at` equals
    `event_time` here — unlike a bar, there is no interval to wait out.

    Kite ticks carry no aggressor flag, so the order-flow features downstream
    derive direction from quotes rather than from classified prints. That is a
    real limitation of this source and is stated in the config warnings, not
    papered over here.
    """
    raw_ms = tick.get("timestamp_ms") or tick.get("exchange_timestamp_ms")
    if raw_ms is None:
        raise ValueError("tick has no timestamp")
    stamp = _iso(int(raw_ms))
    depth = tick.get("depth") or {}
    bids = depth.get("buy") or []
    asks = depth.get("sell") or []

    return CanonicalEventBoundary.create(
        record_id=_record_id("TICK", symbol, stamp, sequence),
        event_type="tick",
        instrument_id=symbol,
        event_time=stamp,
        available_at=stamp,
        source=SOURCE_NAME,
        source_version=SOURCE_VERSION,
        payload={
            "ltp": _num(tick.get("last_price")),
            "volume": _num(tick.get("volume_traded") or tick.get("volume")),
            "oi": _num(tick.get("oi")),
            "bid": _num(bids[0].get("price")) if bids else None,
            "bidqty": _num(bids[0].get("quantity")) if bids else None,
            "ask": _num(asks[0].get("price")) if asks else None,
            "askqty": _num(asks[0].get("quantity")) if asks else None,
        },
        source_timestamp=stamp,
        sequence=sequence,
        provenance={"provider": "Kite", "feed_type": "tick"},
    )
