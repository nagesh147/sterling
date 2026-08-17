def test_replay_contract_causal_callable():
    from app.services.providers.truedata.replay_contract import require_causal_order
    assert callable(require_causal_order)
