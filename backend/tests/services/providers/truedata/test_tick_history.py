"""LiquidityImbalance tick acquisition, persistence, and last-quote sampling."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.engines.adaptive_edge.feature_engine import FeatureStatus
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.liquidity_imbalance import (
    compute_liquidity_imbalance,
    last_quote_at_or_before,
    liquidity_imbalance_at,
)
from app.engines.adaptive_edge.replay import CanonicalEventSequence
from app.services.market_data.truedata import TrueDataHistoricalClient
from app.services.providers.truedata.adapter import TrueDataMarketDataAdapter
from app.services.providers.truedata.tick_history import (
    TickHistoryAcquirer,
    format_history_timestamp,
    nse_session_chunks,
    ticks_to_canonical_sequence,
)
from app.services.providers.truedata.tick_store import TickStore

IST = ZoneInfo("Asia/Kolkata")


def test_naive_truedata_timestamp_is_asia_kolkata_not_utc():
    iso = TrueDataMarketDataAdapter.format_iso_timestamp("2026-08-14 09:15:00")
    parsed = datetime.fromisoformat(iso)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0
    assert iso.startswith("2026-08-14T03:45:00")


def test_explicit_offset_timestamp_is_preserved():
    iso = TrueDataMarketDataAdapter.format_iso_timestamp("2026-08-14T09:15:00+05:30")
    assert iso.startswith("2026-08-14T09:15:00+05:30") or iso.startswith("2026-08-14T03:45:00")


def test_same_second_ticks_get_unique_record_ids():
    raw = {
        "timestamp": "2026-08-13T09:15:00",
        "ltp": 24700,
        "volume": 1,
        "oi": 100,
        "bid": 24699,
        "bidqty": 2600,
        "ask": 24701,
        "askqty": 195,
    }
    a = TrueDataMarketDataAdapter.create_tick_event("NIFTY-I", raw, sequence=0)
    b = TrueDataMarketDataAdapter.create_tick_event("NIFTY-I", raw, sequence=1)
    assert a.record_id != b.record_id
    assert a.sequence == 0
    assert b.sequence == 1


def test_missing_bidask_fields_map_to_none():
    raw = {"timestamp": "2026-08-13T09:15:00", "ltp": 100, "volume": 1, "oi": 0}
    event = TrueDataMarketDataAdapter.create_tick_event("NIFTY-I", raw, sequence=0)
    assert event.payload["bidqty"] is None
    assert event.payload["askqty"] is None


def test_compute_li_valid_and_zero_and_missing():
    value, status = compute_liquidity_imbalance(2600, 195)
    assert status is FeatureStatus.VALID
    assert value == pytest.approx((2600 - 195) / (2600 + 195))
    assert -1.0 <= value <= 1.0

    value, status = compute_liquidity_imbalance(0, 0)
    assert value is None
    assert status is FeatureStatus.MISSING

    value, status = compute_liquidity_imbalance(None, 10)
    assert value is None
    assert status is FeatureStatus.MISSING

    value, status = compute_liquidity_imbalance(-1, 10)
    assert value is None
    assert status is FeatureStatus.MISSING


def test_last_quote_at_or_before_is_causal():
    rows = [
        {"timestamp": "2026-08-13T09:15:00", "ltp": 1, "volume": 1, "oi": 0, "bid": 1, "bidqty": 10, "ask": 2, "askqty": 10},
        {"timestamp": "2026-08-13T09:15:30", "ltp": 1, "volume": 1, "oi": 0, "bid": 1, "bidqty": 20, "ask": 2, "askqty": 5},
        {"timestamp": "2026-08-13T09:16:01", "ltp": 1, "volume": 1, "oi": 0, "bid": 1, "bidqty": 99, "ask": 2, "askqty": 1},
    ]
    events = [
        TrueDataMarketDataAdapter.create_tick_event("NIFTY-I", row, sequence=i)
        for i, row in enumerate(rows)
    ]
    decision = "2026-08-13T03:46:00+00:00"  # 09:16:00 IST
    chosen = last_quote_at_or_before(events, decision)
    assert chosen is not None
    assert chosen.payload["bidqty"] == 20.0
    feature = liquidity_imbalance_at(events, decision)
    assert feature.status is FeatureStatus.VALID
    assert feature.value == pytest.approx((20 - 5) / (20 + 5))
    assert feature.available_at <= decision


def test_format_history_timestamp_matches_v26():
    dt = datetime(2026, 8, 13, 9, 15, tzinfo=IST)
    assert format_history_timestamp(dt) == "260813T09:15:00"


def test_nse_session_chunks_are_ist_sessions():
    start = datetime(2026, 8, 12, 0, 0, tzinfo=IST)
    end = datetime(2026, 8, 13, 23, 59, tzinfo=IST)
    chunks = nse_session_chunks(start, end)
    assert len(chunks) == 2
    assert chunks[0][0].strftime("%y%m%dT%H:%M:%S") == "260812T09:15:00"
    assert chunks[0][1].strftime("%y%m%dT%H:%M:%S") == "260812T15:30:00"


def test_tick_store_round_trip_and_hash(tmp_path):
    store = TickStore(tmp_path / "ticks.sqlite")
    rows = [
        {
            "timestamp": "2026-08-13T09:15:00",
            "ltp": 24700.0,
            "volume": 1.0,
            "oi": 10.0,
            "bid": 24699.0,
            "bidqty": 2600.0,
            "ask": 24701.0,
            "askqty": 195.0,
        }
    ]
    digest = store.upsert("NIFTY-I", rows, request_from="260813T09:15:00", request_to="260813T09:16:00")
    loaded = store.load("NIFTY-I")
    assert len(loaded) == 1
    assert loaded[0]["bidqty"] == 2600.0
    assert store.dataset_sha256("NIFTY-I") == digest
    again = store.upsert("NIFTY-I", rows, request_from="260813T09:15:00", request_to="260813T09:16:00")
    assert again == digest
    assert len(store.load("NIFTY-I")) == 1


@pytest.mark.asyncio
async def test_acquirer_uses_documented_from_to_and_bidask(tmp_path):
    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(
                200,
                json={"access_token": "token-1", "token_type": "bearer", "expires_in": 3600},
                request=request,
            )
        seen.append(str(request.url))
        body = (
            "timestamp,ltp,volume,oi,bid,bidqty,ask,askqty\n"
            "2026-08-13T09:15:00,24700,1,10,24699,2600,24701,195\n"
            "2026-08-13T09:15:00,24701,1,10,24699,2500,24701,200\n"
        )
        return httpx.Response(200, text=body, request=request)

    client = TrueDataHistoricalClient(
        "user", "secret", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    store = TickStore(tmp_path / "ticks.sqlite")
    acquirer = TickHistoryAcquirer(client, store, min_interval_seconds=0.0)
    start = datetime(2026, 8, 13, 9, 15, tzinfo=IST)
    end = datetime(2026, 8, 13, 9, 16, tzinfo=IST)
    result = await acquirer.acquire("NIFTY-I", start, end)
    await client.aclose()

    assert result.row_count == 2
    assert "getticks" in seen[0]
    assert "bidask=1" in seen[0]
    assert "from=260813T09%3A15%3A00" in seen[0]
    assert "to=260813T09%3A16%3A00" in seen[0]

    sequence = ticks_to_canonical_sequence("NIFTY-I", store.load("NIFTY-I"))
    assert len(sequence.events) == 2
    assert sequence.events[0].record_id != sequence.events[1].record_id
    replay = CanonicalEventSequence.from_events(list(reversed(sequence.events)))
    assert replay.sequence_hash == sequence.sequence_hash

    feature = liquidity_imbalance_at(
        sequence.events, "2026-08-13T03:45:30+00:00"
    )
    assert feature.status is FeatureStatus.VALID
    assert FORMULAS["F-101"].status is FormulaStatus.IMPLEMENTED


def test_bar_store_round_trip_and_hash(tmp_path):
    from app.services.providers.truedata.bar_store import BarStore

    store = BarStore(tmp_path / "bars.sqlite")
    rows = [
        {
            "timestamp": "2026-08-13T09:15:00",
            "open": 24700.0,
            "high": 24710.0,
            "low": 24690.0,
            "close": 24705.0,
            "volume": 10.0,
            "oi": 100.0,
        }
    ]
    digest = store.upsert(
        "NIFTY-I", rows, interval="1min", request_from="260813T09:15:00", request_to="260813T09:16:00"
    )
    loaded = store.load("NIFTY-I")
    assert len(loaded) == 1
    assert loaded[0]["close"] == 24705.0
    assert store.dataset_sha256("NIFTY-I") == digest


@pytest.mark.asyncio
async def test_bar_acquirer_uses_documented_getbars(tmp_path):
    from app.services.providers.truedata.bar_history import (
        BarHistoryAcquirer,
        bars_to_canonical_sequence,
    )
    from app.services.providers.truedata.bar_store import BarStore

    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(
                200,
                json={"access_token": "token-1", "token_type": "bearer", "expires_in": 3600},
                request=request,
            )
        seen.append(str(request.url))
        body = (
            "timestamp,open,high,low,close,volume,oi\n"
            "2026-08-13T09:15:00,24700,24710,24690,24705,10,100\n"
        )
        return httpx.Response(200, text=body, request=request)

    client = TrueDataHistoricalClient(
        "user", "secret", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    store = BarStore(tmp_path / "bars.sqlite")
    acquirer = BarHistoryAcquirer(client, store, min_interval_seconds=0.0)
    start = datetime(2026, 8, 13, 9, 15, tzinfo=IST)
    end = datetime(2026, 8, 13, 9, 16, tzinfo=IST)
    result = await acquirer.acquire("NIFTY-I", start, end)
    await client.aclose()

    assert result.row_count == 1
    assert "getbars" in seen[0]
    assert "interval=1min" in seen[0]
    assert "from=260813T09%3A15%3A00" in seen[0]
    sequence = bars_to_canonical_sequence("NIFTY-I", store.load("NIFTY-I"))
    assert len(sequence.events) == 1
    assert sequence.events[0].event_type == "bar"
    assert sequence.events[0].payload["close"] == 24705.0
    assert FORMULAS["F-101"].status is FormulaStatus.IMPLEMENTED
