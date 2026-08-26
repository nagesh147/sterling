def test_provenance_boundary_has_order_check():
    from app.services.providers.truedata.replay_contract import require_causal_order
    import inspect
    assert "record_id" in inspect.getsource(require_causal_order)
