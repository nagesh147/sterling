def test_true_data_source_is_truedata():
    from app.services.providers.truedata.replay_contract import TRUE_DATA_SOURCE
    assert TRUE_DATA_SOURCE == "truedata"
