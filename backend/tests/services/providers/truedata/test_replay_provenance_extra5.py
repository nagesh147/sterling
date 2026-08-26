def test_true_data_version_is_v26():
    from app.services.providers.truedata.replay_contract import TRUE_DATA_VERSION
    assert TRUE_DATA_VERSION == "2.6"
