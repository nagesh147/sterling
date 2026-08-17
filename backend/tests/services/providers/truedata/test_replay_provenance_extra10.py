def test_tick_store_dataset_hash_is_canonical(tmp_path):
    from app.services.providers.truedata.tick_store import TickStore
    s = TickStore(tmp_path / "t.sqlite")
    s.upsert("NIFTY-I", [{"timestamp":"2026-08-17 09:15:00","ltp":1}], request_from="x", request_to="y")
    digest = s.dataset_sha256("NIFTY-I")
    assert isinstance(digest, str) and len(digest) == 64
