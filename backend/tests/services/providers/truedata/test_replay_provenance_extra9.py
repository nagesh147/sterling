def test_bar_store_dataset_hash_includes_provenance(tmp_path):
    from app.services.providers.truedata.bar_store import BarStore
    s = BarStore(tmp_path / "b.sqlite")
    s.upsert("NIFTY-I", [{"timestamp":"2026-08-17 09:15:00","close":1}], interval="1min", request_from="x", request_to="y")
    first = s.dataset_sha256("NIFTY-I")
    assert isinstance(first, str) and len(first) == 64
