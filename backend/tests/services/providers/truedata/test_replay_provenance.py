from __future__ import annotations

import pytest

from app.engines.adaptive_edge.event_boundary import CanonicalEventBoundary
from app.engines.adaptive_edge.replay import CanonicalEventSequence
from app.services.providers.truedata.adapter import TrueDataMarketDataAdapter
from app.services.providers.truedata.bar_store import BarStore
from app.services.providers.truedata.replay_contract import require_causal_order, require_truedata_sequence
from app.services.providers.truedata.tick_store import TickStore


def _bar(ts: str, close: float, **metadata: object) -> dict[str, object]:
    return {"timestamp": ts, "open": close - 1, "high": close + 1, "low": close - 2, "close": close, "volume": 1000, "oi": 0, **metadata}


def test_bar_store_preserves_provider_provenance(tmp_path) -> None:
    store = BarStore(tmp_path / "bars.sqlite")
    store.upsert("NIFTY-I", [_bar("2026-08-17 09:15:00", 24700)], interval="1min", request_from="2026-08-17 09:15:00", request_to="2026-08-17 09:16:00")
    row = store.load("NIFTY-I")[0]
    assert row["source"] == "truedata"
    assert row["source_version"] == "2.6"


def test_tick_store_preserves_provider_provenance(tmp_path) -> None:
    store = TickStore(tmp_path / "ticks.sqlite")
    store.upsert("NIFTY-I", [{"timestamp": "2026-08-17 09:15:00", "ltp": 24700}], request_from="2026-08-17 09:15:00", request_to="2026-08-17 09:16:00")
    row = store.load("NIFTY-I")[0]
    assert row["source"] == "truedata"
    assert row["source_version"] == "2.6"


def test_adapter_rejects_synthetic_relabeling() -> None:
    with pytest.raises(ValueError, match="provenance source"):
        TrueDataMarketDataAdapter.create_bar_event("NIFTY-I", _bar("2026-08-17 09:15:00", 24700, source="synthetic"))


def test_adapter_rejects_wrong_provider_version() -> None:
    with pytest.raises(ValueError, match="provenance version"):
        TrueDataMarketDataAdapter.create_tick_event("NIFTY-I", {"timestamp": "2026-08-17 09:15:00", "ltp": 24700, "source_version": "1.0"})


def test_replay_contract_rejects_synthetic_event() -> None:
    event = CanonicalEventBoundary.create(record_id="SYNTH-1", event_type="bar", instrument_id="NIFTY-I", event_time="2026-08-17T03:45:00+00:00", available_at="2026-08-17T03:45:00+00:00", source="synthetic", source_version="1.0", payload={"close": 24700.0}, source_timestamp="2026-08-17T03:45:00+00:00")
    with pytest.raises(ValueError, match="non-TrueData provenance"):
        require_truedata_sequence(CanonicalEventSequence.from_events([event]), "bar")


def test_replay_contract_enforces_causal_order() -> None:
    event = CanonicalEventBoundary.create(record_id="TD-1", event_type="bar", instrument_id="NIFTY-I", event_time="2026-08-17T03:45:00+00:00", available_at="2026-08-17T03:44:59+00:00", source="truedata", source_version="2.6", payload={"close": 24700.0}, source_timestamp="2026-08-17T03:45:00+00:00")
    with pytest.raises(ValueError, match="causal availability"):
        require_causal_order(CanonicalEventSequence.from_events([event]), "bar")
