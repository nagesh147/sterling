def test_tick_replay_cache_round_trip_is_not_empty(tmp_path):
    from app.services.providers.truedata.tick_store import TickStore
    s = TickStore(tmp_path / "t.sqlite")
    s.upsert("NIFTY-I", [{"timestamp":"2026-08-17 09:15:00","ltp":1}], request_from="x", request_to="y")
    assert s.load("NIFTY-I")
