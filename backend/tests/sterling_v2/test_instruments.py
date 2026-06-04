from app.engines.sterling_v2.instruments import build_instrument_signals


def _base_sig(side=1, entry=60000.0, atr=900.0, conviction=30.0):
    """Mirror research.latest_v2_signal: stop=2xATR, target=3.5xATR from entry."""
    stop = entry - 2.0 * atr if side == 1 else entry + 2.0 * atr
    target = entry + 3.5 * atr if side == 1 else entry - 3.5 * atr
    return {"side": side, "entry": entry, "stop": stop, "target": target,
            "atr": atr, "conviction": conviction, "current_price": entry,
            "bar_time": "2026-01-01 00:00:00"}


def _of(sigs, itype):
    return next(s for s in sigs if s["instrument_type"] == itype)


def test_leverage_cap_differs_by_profile():
    # stop_pct = 2*900/60000 = 3% -> L_max_liq = 1/0.04 = 25, so the PROFILE cap binds.
    sig = _base_sig()
    scal, _ = build_instrument_signals(sig, "ma_crossover", "Scalping")
    intr, _ = build_instrument_signals(sig, "ma_crossover", "Intraday")
    aggr, _ = build_instrument_signals(sig, "ma_crossover", "Aggressive")
    assert _of(scal, "futures")["leverage"] == 3.0
    assert _of(intr, "futures")["leverage"] == 5.0
    assert _of(aggr, "futures")["leverage"] == 10.0


def test_intraday_trailing_uses_same_cap_as_intraday():
    sig = _base_sig()
    trail, _ = build_instrument_signals(sig, "ma_crossover", "Intraday_Trailing")
    assert _of(trail, "futures")["leverage"] == 5.0  # not mis-matched to Scalping/Aggressive


def test_liquidation_caps_leverage_below_profile_when_stop_is_wide():
    # huge ATR -> stop_pct ~ 30% -> L_max_liq ~ 1/0.31 ~ 3.2, below the Aggressive cap of 10.
    sig = _base_sig(atr=9000.0)
    aggr, _ = build_instrument_signals(sig, "ma_crossover", "Aggressive")
    assert _of(aggr, "futures")["leverage"] < 10.0


def test_otm_option_is_cheaper_and_breakeven_includes_strike_gap():
    entry = _base_sig()["entry"]
    high, _ = build_instrument_signals(_base_sig(conviction=30.0), "ma_crossover", "Intraday")
    low, _ = build_instrument_signals(_base_sig(conviction=5.0), "ma_crossover", "Intraday")
    ho, lo = _of(high, "options"), _of(low, "options")
    assert ho["strike"] != entry          # conv 0.75 > 0.6 -> OTM
    assert lo["strike"] == entry          # conv 0.125 -> ATM
    assert ho["premium"] < lo["premium"]  # OTM is cheaper
    # breakeven must reflect the distance to the OTM strike, not just premium/S
    assert ho["breakeven_pct"] > ho["premium"] / entry


def test_put_strike_is_below_spot_for_shorts():
    sigs, _ = build_instrument_signals(_base_sig(side=-1, conviction=30.0), "ma_crossover", "Intraday")
    opt = _of(sigs, "options")
    assert opt["option_type"] == "put"
    assert opt["strike"] < _base_sig(side=-1)["entry"]  # OTM put sits below spot


def test_idle_signal_returns_three_bare_instruments():
    idle = {"side": 0, "entry": 60000.0, "stop": None, "target": None,
            "atr": 0.0, "conviction": 0.0, "current_price": 60000.0, "bar_time": ""}
    sigs, best = build_instrument_signals(idle, "ma_crossover", "Intraday")
    assert [s["instrument_type"] for s in sigs] == ["spot", "futures", "options"]
    assert "leverage" not in _of(sigs, "futures")  # no plan -> no instrument math
    assert best == "spot"


def test_picker_returns_one_of_the_three_instruments():
    sigs, best = build_instrument_signals(_base_sig(), "ma_crossover", "Intraday")
    assert best in {"spot", "futures", "options"}


def test_option_expiry_is_a_realistic_listed_tenor():
    # A 4h, 3.5xATR target needs room: expiry must round up to a listed weekly+
    # tenor, never the old sub-2-day proxy that made premiums unrealistically cheap.
    opt = _of(build_instrument_signals(_base_sig(), "ma_crossover", "Intraday")[0], "options")
    assert opt["expiry_days"] >= 7.0
    assert opt["expiry_days"] in {7.0, 14.0, 30.0}


def test_trend_signal_routes_to_futures_not_options():
    # ATM, moderate-conviction trend signal: with the OLD ~1.5d expiry the premium
    # was so cheap that move_be dominated and EVERYTHING routed to options. A
    # realistic expiry restores leveraged futures as the pick for a plain trend.
    _, best = build_instrument_signals(_base_sig(conviction=20.0), "ma_crossover", "Intraday")
    assert best == "futures"
