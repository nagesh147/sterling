def test_replay_contract_is_importable():
    from app.services.providers.truedata.replay_contract import require_truedata_sequence
    assert callable(require_truedata_sequence)
