def test_provenance_boundary_has_causal_check():
    from app.services.providers.truedata.replay_contract import require_causal_order
    import inspect
    assert "available_at" in inspect.getsource(require_causal_order)
