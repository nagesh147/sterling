from app.services.providers.truedata.bar_store import BarStore
from app.services.providers.truedata.tick_store import TickStore


def test_bar_store_preserves_explicit_synthetic_provenance(tmp_path):
    s = BarStore(tmp_path / "b.sqlite")
    s.upsert("NIFTY-I", [{"timestamp": "2026-08-17 09:15:00", "close": 1, "source": "synthetic", "source_version": "1.0"}], interval="1min", request_from="x", request_to="y")
    row = s.load("NIFTY-I")[0]
    assert (row["source"], row["source_version"]) == ("synthetic", "1.0")


def test_tick_store_preserves_explicit_synthetic_provenance(tmp_path):
    s = TickStore(tmp_path / "t.sqlite")
    s.upsert("NIFTY-I", [{"timestamp": "2026-08-17 09:15:00", "ltp": 1, "source": "synthetic", "source_version": "1.0"}], request_from="x", request_to="y")
    row = s.load("NIFTY-I")[0]
    assert (row["source"], row["source_version"]) == ("synthetic", "1.0")
