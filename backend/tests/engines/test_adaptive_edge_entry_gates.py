from app.engines.adaptive_edge.entry_gates import buy_ce_gate, buy_pe_gate


def test_buy_ce_requires_all_exact_conditions():
    kwargs = dict(
        data_ok=True,
        directional_edge_ok=True,
        ev_ce=1.0,
        conservative_ev_ce=0.5,
        liquidity_ok=True,
        slippage_ok=True,
        risk_ok=True,
    )
    assert buy_ce_gate(**kwargs)
    for field in kwargs:
        failed = dict(kwargs)
        failed[field] = False if isinstance(kwargs[field], bool) else -0.1
        assert not buy_ce_gate(**failed)


def test_buy_ce_strictly_requires_positive_economic_values():
    kwargs = dict(
        data_ok=True,
        directional_edge_ok=True,
        ev_ce=1.0,
        conservative_ev_ce=1.0,
        liquidity_ok=True,
        slippage_ok=True,
        risk_ok=True,
    )
    assert not buy_ce_gate(**{**kwargs, "ev_ce": 0.0})
    assert not buy_ce_gate(**{**kwargs, "conservative_ev_ce": 0.0})


def test_buy_pe_is_analogous():
    kwargs = dict(
        data_ok=True,
        directional_edge_ok=True,
        ev_pe=1.0,
        conservative_ev_pe=1.0,
        liquidity_ok=True,
        slippage_ok=True,
        risk_ok=True,
    )
    assert buy_pe_gate(**kwargs)
    assert not buy_pe_gate(**{**kwargs, "directional_edge_ok": False})
