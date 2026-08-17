from app.services.providers.truedata.bar_store import BarStore
from app.services.providers.truedata.tick_store import TickStore


def test_bar_store_provenance_round_trip(tmp_path):
    s = BarStore(tmp_path / "b.sqlite")
    s.upsert("NIFTY-I", [{"timestamp": "2026-08-17 09:15:00", "close": 1}], interval="1min", request_from="x", request_to="y")
    row = s.load("NIFTY-I")[0]
    assert (row["source"], row["source_version"]) == ("truedata", "2.6")


def test_tick_store_provenance_round_trip(tmp_path):
    s = TickStore(tmp_path / "t.sqlite")
    s.upsert("NIFTY-I", [{"timestamp": "2026-08-17 09:15:00", "ltp": 1}], request_from="x", request_to="y")
    row = s.load("NIFTY-I")[0]
    assert (row["source"], row["source_version"]) == ("truedata", "2.6")
