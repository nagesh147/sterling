from app.services.providers.truedata.bar_store import BarStore
from app.services.providers.truedata.tick_store import TickStore


def test_bar_store_keeps_explicit_source(tmp_path):
    store = BarStore(tmp_path / "bars.sqlite")
    store.upsert("NIFTY-I", [{"timestamp": "2026-08-17 09:15:00", "close": 24700, "source": "synthetic", "source_version": "1.0"}], interval="1min", request_from="x", request_to="y")
    row = store.load("NIFTY-I")[0]
    assert row["source"] == "synthetic"
    assert row["source_version"] == "1.0"


def test_tick_store_keeps_explicit_source(tmp_path):
    store = TickStore(tmp_path / "ticks.sqlite")
    store.upsert("NIFTY-I", [{"timestamp": "2026-08-17 09:15:00", "ltp": 24700, "source": "synthetic", "source_version": "1.0"}], request_from="x", request_to="y")
    row = store.load("NIFTY-I")[0]
    assert row["source"] == "synthetic"
    assert row["source_version"] == "1.0"
