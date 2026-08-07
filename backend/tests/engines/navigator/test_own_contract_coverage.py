"""Navigator's own strike ladder and expiry cycles.

Before these fields existed, `navigator/runtime` passed the Kite engine's
`strike_moneyness` and expiry lists unconditionally, whatever Navigator's scan
scope was. So a user editing strike coverage on a page titled "SuperTrend"
silently moved Navigator too, and there was no way to run the two engines on
different contract coverage — which is a reasonable thing to want from two
engines that look for different things.

`None` still means "follow the Kite engine", so every existing config is
unchanged.
"""
from app.engines.navigator.schemas import NavigatorConfigModel


def test_contract_fields_default_to_following_the_engine():
    cfg = NavigatorConfigModel()
    assert cfg.strike_moneyness is None
    assert cfg.scan_expiries_indices is None
    assert cfg.scan_expiries_stocks is None


def test_navigator_can_hold_its_own_ladder():
    cfg = NavigatorConfigModel(strike_moneyness=["ATM"], scan_expiries_indices=["weekly"])
    assert cfg.strike_moneyness == ["ATM"]
    assert cfg.scan_expiries_indices == ["weekly"]


def test_contract_coverage_is_independent_of_the_instrument_scope():
    """The two are separate choices.

    Sharing the instrument universe and sharing the contract ladder used to be
    the same flag, which is what made "scan scope" confusing: there was no way
    to say "same instruments, different strikes".
    """
    cfg = NavigatorConfigModel(
        scan_scope_mode="shared",          # same instruments as SuperTrend…
        strike_moneyness=["ATM"],          # …but its own, narrower ladder
    )
    assert cfg.scan_scope_mode == "shared"
    assert cfg.strike_moneyness == ["ATM"]


def test_runtime_prefers_navigator_ladder_over_the_engine_one():
    """Mirrors the selection in navigator/runtime.scan_user."""
    nav = NavigatorConfigModel(strike_moneyness=["ATM"], scan_expiries_indices=["monthly"])
    engine_moneyness = ["ITM1", "ATM", "OTM1"]
    engine_index_expiries = ["weekly", "monthly"]

    chosen_moneyness = (nav.strike_moneyness
                        if nav.strike_moneyness is not None else engine_moneyness)
    chosen_expiries = (nav.scan_expiries_indices
                       if nav.scan_expiries_indices is not None else engine_index_expiries)

    assert chosen_moneyness == ["ATM"]
    assert chosen_expiries == ["monthly"]


def test_runtime_falls_back_to_the_engine_when_navigator_has_none():
    nav = NavigatorConfigModel()
    engine_moneyness = ["ITM1", "ATM", "OTM1"]

    chosen = nav.strike_moneyness if nav.strike_moneyness is not None else engine_moneyness

    assert chosen == engine_moneyness
