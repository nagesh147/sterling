def test_replay_contract_is_fail_closed():
    from app.services.providers.truedata.replay_contract import require_truedata_sequence
    import inspect
    assert "source" in inspect.getsource(require_truedata_sequence)
