"""TrueData Market Data Adapter to CanonicalMarketEvent.

Converts raw TrueData historical bars, ticks, and option chain records into
immutable CanonicalMarketEvent objects crossing into the Adaptive Edge boundary.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, List, Mapping

from app.engines.adaptive_edge.event_boundary import CanonicalEventBoundary, CanonicalMarketEvent


class TrueDataMarketDataAdapter:
    """Adapter translating TrueData V2.6 raw data objects to CanonicalMarketEvent."""

    SOURCE_NAME = "truedata"
    SOURCE_VERSION = "2.6"

    @classmethod
    def format_iso_timestamp(cls, raw_ts: str) -> str:
        """Parse raw TrueData timestamp string to ISO-8601 string with UTC timezone offset."""
        if not raw_ts:
            raise ValueError("Raw timestamp cannot be empty")

        clean_ts = raw_ts.strip().replace("Z", "+00:00")
        dt: datetime

        # Handle various documented TrueData formats:
        # e.g., "2026-08-14 12:00:00", "2026-08-14T12:00:00", "2026-08-14 12:00:00.123456"
        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(clean_ts, fmt)
                dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError:
                continue

        # Fallback to datetime.fromisoformat if already ISO formatted
        try:
            dt = datetime.fromisoformat(clean_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError as exc:
            raise ValueError(f"Invalid TrueData timestamp format: {raw_ts}") from exc

    @classmethod
    def create_bar_event(
        cls,
        symbol: str,
        bar_record: Mapping[str, Any],
        *,
        receipt_time_iso: str | None = None,
        sequence: int | None = None,
    ) -> CanonicalMarketEvent:
        """Convert a raw TrueData bar record to CanonicalMarketEvent."""
        raw_time = str(bar_record.get("timestamp") or bar_record.get("time") or "")
        event_time_iso = cls.format_iso_timestamp(raw_time)

        # Causal requirement: available_at >= event_time. If no receipt_time provided,
        # available_at equals event_time.
        available_at_iso = receipt_time_iso or event_time_iso
        if available_at_iso < event_time_iso:
            available_at_iso = event_time_iso

        record_id = f"TD-BAR-{symbol}-{hashlib.sha256((symbol + event_time_iso).encode()).hexdigest()[:12]}"

        try:
            payload = {
                "open": float(bar_record.get("open", 0.0)),
                "high": float(bar_record.get("high", 0.0)),
                "low": float(bar_record.get("low", 0.0)),
                "close": float(bar_record.get("close", 0.0)),
                "volume": float(bar_record.get("volume", 0.0)),
                "oi": float(bar_record.get("oi", 0.0)),
            }
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid TrueData bar payload: {exc}") from exc

        return CanonicalEventBoundary.create(
            record_id=record_id,
            event_type="bar",
            instrument_id=symbol,
            event_time=event_time_iso,
            available_at=available_at_iso,
            source=cls.SOURCE_NAME,
            source_version=cls.SOURCE_VERSION,
            payload=payload,
            source_timestamp=event_time_iso,
            receipt_timestamp=receipt_time_iso,
            sequence=sequence,
            provenance={
                "provider": "TrueData",
                "feed_type": "historical_bar",
            },
        )

    @classmethod
    def create_tick_event(
        cls,
        symbol: str,
        tick_record: Mapping[str, Any],
        *,
        receipt_time_iso: str | None = None,
        sequence: int | None = None,
    ) -> CanonicalMarketEvent:
        """Convert a raw TrueData tick record to CanonicalMarketEvent."""
        raw_time = str(tick_record.get("timestamp") or tick_record.get("time") or "")
        event_time_iso = cls.format_iso_timestamp(raw_time)

        available_at_iso = receipt_time_iso or event_time_iso
        if available_at_iso < event_time_iso:
            available_at_iso = event_time_iso

        record_id = f"TD-TICK-{symbol}-{hashlib.sha256((symbol + event_time_iso + str(sequence)).encode()).hexdigest()[:12]}"

        return CanonicalEventBoundary.create(
            record_id=record_id,
            event_type="tick",
            instrument_id=symbol,
            event_time=event_time_iso,
            available_at=available_at_iso,
            source=cls.SOURCE_NAME,
            source_version=cls.SOURCE_VERSION,
            payload={
                "ltp": float(tick_record.get("ltp", 0.0)),
                "volume": float(tick_record.get("volume", 0.0)),
                "oi": float(tick_record.get("oi", 0.0)),
                "bid": float(tick_record.get("bid", 0.0)) if "bid" in tick_record else None,
                "bidqty": float(tick_record.get("bidqty", 0.0)) if "bidqty" in tick_record else None,
                "ask": float(tick_record.get("ask", 0.0)) if "ask" in tick_record else None,
                "askqty": float(tick_record.get("askqty", 0.0)) if "askqty" in tick_record else None,
            },
            source_timestamp=event_time_iso,
            receipt_timestamp=receipt_time_iso,
            sequence=sequence,
            provenance={
                "provider": "TrueData",
                "feed_type": "historical_tick",
            },
        )
