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


# ── implied_vol (Newton-Raphson + bisection fallback) ─────────────────────────
from app.services.kite_engine.greeks import implied_vol, bs_price  # noqa: E402


def test_implied_vol_round_trips_when_well_conditioned():
    """Price at a known IV, solve it back. Only asserts where the IV is actually
    identifiable from price — i.e. vega is non-trivial. Deep-ITM/OTM low-vol options
    have ~zero vega, so IV is unrecoverable from premium for ANY solver; those are
    excluded (their greeks are IV-insensitive anyway). Guards the Newton solver."""
    import random
    random.seed(11)
    checked = 0
    for _ in range(4000):
        ot = random.choice(["CE", "PE"])
        spot = random.uniform(50, 25000)
        strike = spot * random.uniform(0.8, 1.2)
        dte = random.uniform(1.0, 90)
        iv0 = random.uniform(0.05, 2.5)
        price = bs_price(spot=spot, strike=strike, dte_days=dte, iv=iv0, option_type=ot)
        if price < 0.05:
            continue
        intrinsic = max(0.0, (spot - strike) if ot == "CE" else (strike - spot))
        if price < intrinsic - 1e-6:       # European value below undiscounted intrinsic
            continue                       # → solver returns 0.0 by contract (guarded)
        g = black_scholes_greeks(spot=spot, strike=strike, dte_days=dte, iv=iv0, option_type=ot)
        if g.vega < 0.01 * spot / 100.0:   # IV ill-conditioned here — not recoverable
            continue
        iv = implied_vol(price=price, spot=spot, strike=strike, dte_days=dte, option_type=ot)
        assert abs(iv - iv0) < 1e-3, (ot, spot, strike, dte, iv0, iv, price)
        checked += 1
    assert checked > 1000


def test_implied_vol_rejects_below_intrinsic():
    # price under intrinsic is unsolvable → 0.0 (unchanged contract)
    assert implied_vol(price=0.01, spot=120, strike=100, dte_days=30, option_type="CE") == 0.0
    assert implied_vol(price=0.0, spot=100, strike=100, dte_days=30, option_type="CE") == 0.0


def test_implied_vol_converges_at_high_vol():
    p = bs_price(spot=20000, strike=20000, dte_days=7, iv=1.8, option_type="CE")
    assert abs(implied_vol(price=p, spot=20000, strike=20000, dte_days=7, option_type="CE") - 1.8) < 1e-3
