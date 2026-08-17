"""TrueData Market Data Adapter to CanonicalMarketEvent.

Converts TrueData historical bars, ticks, and option chain records into
immutable CanonicalMarketEvent objects. Cached rows may carry provenance;
mismatched provenance is rejected instead of being silently relabeled.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from app.engines.adaptive_edge.event_boundary import CanonicalEventBoundary, CanonicalMarketEvent

_PROVIDER_TZ = ZoneInfo("Asia/Kolkata")


def _optional_float(record: Mapping[str, Any], key: str) -> float | None:
    if key not in record:
        return None
    value = record.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid TrueData numeric field {key}: {value}") from exc


def _require_provider_provenance(record: Mapping[str, Any], *, label: str) -> None:
    source = record.get("source")
    version = record.get("source_version")
    if source is not None and source != "truedata":
        raise ValueError(f"Invalid {label} provenance source: {source!r}")
    if version is not None and version != "2.6":
        raise ValueError(f"Invalid {label} provenance version: {version!r}")


class TrueDataMarketDataAdapter:
    """Adapter translating TrueData V2.6 raw data objects to CanonicalMarketEvent."""

    SOURCE_NAME = "truedata"
    SOURCE_VERSION = "2.6"
    PROVIDER_TIMEZONE = "Asia/Kolkata"

    @classmethod
    def format_iso_timestamp(cls, raw_ts: str) -> str:
        if not raw_ts:
            raise ValueError("Raw timestamp cannot be empty")
        clean_ts = raw_ts.strip()
        dt: datetime | None = None
        if clean_ts.endswith("Z") or "+" in clean_ts[10:] or clean_ts.count("-") > 2:
            try:
                dt = datetime.fromisoformat(clean_ts.replace("Z", "+00:00"))
            except ValueError:
                dt = None
        if dt is None:
            for fmt in (
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%d/%m/%Y %H:%M:%S",
            ):
                try:
                    dt = datetime.strptime(clean_ts, fmt)
                    break
                except ValueError:
                    continue
        if dt is None:
            raise ValueError(f"Invalid TrueData timestamp format: {raw_ts}")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_PROVIDER_TZ)
        return dt.astimezone(timezone.utc).isoformat()

    @classmethod
    def create_bar_event(cls, symbol: str, bar_record: Mapping[str, Any], *, receipt_time_iso: str | None = None, sequence: int | None = None) -> CanonicalMarketEvent:
        _require_provider_provenance(bar_record, label="bar")
        raw_time = str(bar_record.get("timestamp") or bar_record.get("time") or "")
        event_time_iso = cls.format_iso_timestamp(raw_time)
        available_at_iso = receipt_time_iso or event_time_iso
        if available_at_iso < event_time_iso:
            raise ValueError("TrueData bar violates causal availability")
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
        return CanonicalEventBoundary.create(record_id=record_id, event_type="bar", instrument_id=symbol, event_time=event_time_iso, available_at=available_at_iso, source=cls.SOURCE_NAME, source_version=cls.SOURCE_VERSION, payload=payload, source_timestamp=event_time_iso, receipt_timestamp=receipt_time_iso, sequence=sequence, provenance={"provider": "TrueData", "feed_type": "historical_bar"})

    @classmethod
    def create_tick_event(cls, symbol: str, tick_record: Mapping[str, Any], *, receipt_time_iso: str | None = None, sequence: int | None = None) -> CanonicalMarketEvent:
        _require_provider_provenance(tick_record, label="tick")
        raw_time = str(tick_record.get("timestamp") or tick_record.get("time") or "")
        event_time_iso = cls.format_iso_timestamp(raw_time)
        available_at_iso = receipt_time_iso or event_time_iso
        if available_at_iso < event_time_iso:
            raise ValueError("TrueData tick violates causal availability")
        ordinal = 0 if sequence is None else sequence
        record_id = "TD-TICK-" + symbol + "-" + hashlib.sha256(f"{symbol}|{event_time_iso}|{ordinal}".encode()).hexdigest()[:12]
        return CanonicalEventBoundary.create(record_id=record_id, event_type="tick", instrument_id=symbol, event_time=event_time_iso, available_at=available_at_iso, source=cls.SOURCE_NAME, source_version=cls.SOURCE_VERSION, payload={"ltp": _optional_float(tick_record, "ltp") or 0.0, "volume": _optional_float(tick_record, "volume") or 0.0, "oi": _optional_float(tick_record, "oi") or 0.0, "bid": _optional_float(tick_record, "bid"), "bidqty": _optional_float(tick_record, "bidqty"), "ask": _optional_float(tick_record, "ask"), "askqty": _optional_float(tick_record, "askqty")}, source_timestamp=event_time_iso, receipt_timestamp=receipt_time_iso, sequence=ordinal, provenance={"provider": "TrueData", "feed_type": "historical_tick", "provider_timezone": cls.PROVIDER_TIMEZONE, "provider_timestamp": raw_time})
