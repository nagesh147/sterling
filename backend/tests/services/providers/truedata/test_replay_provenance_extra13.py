def test_replay_contract_exports_source_and_version():
    from app.services.providers.truedata import replay_contract
    assert replay_contract.TRUE_DATA_SOURCE
    assert replay_contract.TRUE_DATA_VERSION
