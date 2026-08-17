def test_replay_provenance_contract_imports():
    from app.services.providers.truedata.replay_contract import TRUE_DATA_SOURCE, TRUE_DATA_VERSION
    assert TRUE_DATA_SOURCE == "truedata"
    assert TRUE_DATA_VERSION == "2.6"
