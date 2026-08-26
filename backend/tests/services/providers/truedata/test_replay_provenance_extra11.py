def test_provenance_round_trip_is_not_empty(tmp_path):
    from app.services.providers.truedata.bar_store import BarStore
    s = BarStore(tmp_path / "b.sqlite")
    s.upsert("NIFTY-I", [{"timestamp":"2026-08-17 09:15:00","close":1}], interval="1min", request_from="x", request_to="y")
    assert s.load("NIFTY-I")
