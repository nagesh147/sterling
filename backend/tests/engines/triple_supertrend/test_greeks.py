from app.services.kite_engine.greeks import black_scholes_greeks


def test_atm_call_put_delta_relationship():
    call = black_scholes_greeks(spot=100, strike=100, dte_days=30, iv=0.2, option_type="CE")
    put = black_scholes_greeks(spot=100, strike=100, dte_days=30, iv=0.2, option_type="PE")
    # ATM call delta ~0.5+, put delta ~-0.5; call - put delta ≈ 1 (put-call parity in delta)
    assert 0.45 < call.delta < 0.65
    assert -0.55 < put.delta < -0.35
    assert abs((call.delta - put.delta) - 1.0) < 0.02
    # shared, positive gamma/vega; negative theta (time decay) for a long option
    assert call.gamma > 0 and put.gamma > 0
    assert call.vega > 0 and put.vega > 0
    assert call.theta < 0 and put.theta < 0
    assert abs(call.gamma - put.gamma) < 1e-9  # gamma identical for call/put


def test_deep_itm_call_delta_near_one():
    g = black_scholes_greeks(spot=200, strike=100, dte_days=30, iv=0.2, option_type="CE")
    assert g.delta > 0.95


def test_expired_option_is_intrinsic():
    itm = black_scholes_greeks(spot=110, strike=100, dte_days=0, iv=0.2, option_type="CE")
    otm = black_scholes_greeks(spot=90, strike=100, dte_days=0, iv=0.2, option_type="CE")
    assert itm.delta == 1.0 and otm.delta == 0.0
    assert itm.gamma == 0.0 and itm.vega == 0.0 and itm.theta == 0.0


def test_implied_vol_round_trips():
    from app.services.kite_engine.greeks import bs_price, implied_vol
    px = bs_price(spot=100, strike=100, dte_days=30, iv=0.22, option_type="CE")
    iv = implied_vol(price=px, spot=100, strike=100, dte_days=30, option_type="CE")
    assert abs(iv - 0.22) < 0.005


def test_implied_vol_below_intrinsic_returns_zero():
    from app.services.kite_engine.greeks import implied_vol
    # price below intrinsic (110-100=10) is unsolvable
    assert implied_vol(price=5.0, spot=110, strike=100, dte_days=30, option_type="CE") == 0.0
