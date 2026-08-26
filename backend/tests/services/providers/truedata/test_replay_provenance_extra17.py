def test_replay_contract_source_constant_is_stable():
    from app.services.providers.truedata.replay_contract import TRUE_DATA_SOURCE
    assert TRUE_DATA_SOURCE == "truedata"
