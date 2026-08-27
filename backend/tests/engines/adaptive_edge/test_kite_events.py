"""Kite candles to CanonicalMarketEvent.

The pipeline orders and gates everything on `available_at`, so the tests that
matter here are the causality ones: a bar must not be available before it closed,
because that is the difference between a causal backtest and one that trades on
information it could not have had.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.kite_events import (
    INTERVAL_SECONDS,
    bar_event,
    bar_events,
    interval_seconds,
    tick_event,
)

BASE_MS = 1_756_100_000_000


def _candle(offset_bars: int = 0, interval_s: int = 60, **over):
    px = 25_000 + offset_bars
    row = {"timestamp_ms": BASE_MS + offset_bars * interval_s * 1000,
           "open": px, "high": px + 8, "low": px - 4, "close": px + 6, "volume": 1_000}
    row.update(over)
    return row


def _seconds_between(a: str, b: str) -> float:
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()


# ------------------------------------------------------------- causality

@pytest.mark.parametrize("interval", sorted(INTERVAL_SECONDS))
def test_a_bar_becomes_available_when_it_closes_not_when_it_opens(interval):
    """Kite timestamps a candle at its start. Treating that as availability
    claims the close was known a whole interval before it existed."""
    event = bar_event("NIFTY", _candle(), interval=interval)
    assert _seconds_between(event.event_time, event.available_at) == INTERVAL_SECONDS[interval]
    assert event.available_at > event.event_time


def test_an_unknown_interval_raises_rather_than_guessing():
    """Guessing short would republish the lookahead this module prevents."""
    with pytest.raises(ValueError, match="unknown Kite interval"):
        interval_seconds("7minute")


def test_a_tick_is_available_when_observed():
    """Unlike a bar there is no interval to wait out."""
    event = tick_event("NIFTY", {"timestamp_ms": BASE_MS, "last_price": 120.0})
    assert event.available_at == event.event_time


# ----------------------------------------------------------------- shape

def test_the_payload_carries_what_the_structure_builder_reads():
    payload = dict(bar_event("NIFTY", _candle()).payload)
    assert set(payload) >= {"open", "high", "low", "close", "volume", "oi"}
    assert payload["close"] == 25_006


def test_missing_ohl_falls_back_to_close_rather_than_zero():
    """A zero high would make every range calculation nonsense."""
    payload = dict(bar_event("NIFTY", {"timestamp_ms": BASE_MS, "close": 120.0}).payload)
    assert payload["open"] == payload["high"] == payload["low"] == 120.0


def test_provenance_says_kite_not_truedata():
    event = bar_event("NIFTY", _candle())
    assert event.source == "kite"
    assert event.provenance["provider"] == "Kite"


def test_a_candle_without_a_timestamp_is_refused():
    with pytest.raises(ValueError, match="no timestamp"):
        bar_event("NIFTY", {"close": 120.0})


# ---------------------------------------------------------------- series

def test_a_series_is_ordered_by_availability():
    shuffled = [_candle(5), _candle(1), _candle(3), _candle(0)]
    events = bar_events("NIFTY", shuffled, interval="minute")
    assert [e.available_at for e in events] == sorted(e.available_at for e in events)


def test_the_same_bar_twice_is_recorded_once():
    """A duplicated bar would double its weight in every rolling window."""
    assert len(bar_events("NIFTY", [_candle(1), _candle(1)], interval="minute")) == 1


def test_one_malformed_row_does_not_discard_the_series():
    rows = [_candle(0), {"close": 1.0}, _candle(1)]
    assert len(bar_events("NIFTY", rows, interval="minute")) == 2


def test_an_empty_series_is_empty_not_an_error():
    assert bar_events("NIFTY", [], interval="minute") == []


def test_record_ids_are_stable_across_calls():
    """Replay compares by record id, so an unstable id breaks determinism."""
    first = bar_events("NIFTY", [_candle(2)], interval="minute")[0]
    second = bar_events("NIFTY", [_candle(2)], interval="minute")[0]
    assert first.record_id == second.record_id


def test_different_bars_get_different_ids():
    events = bar_events("NIFTY", [_candle(0), _candle(1)], interval="minute")
    assert events[0].record_id != events[1].record_id
