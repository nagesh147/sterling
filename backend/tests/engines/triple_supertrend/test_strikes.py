from app.services.kite_engine.strikes import OptionPick, pick_strike


def _chain(strikes, otype, expiry="2026-06-26", dte=8):
    return [
        {
            "strike": float(s),
            "option_type": otype,  # "call" | "put"
            "expiry_date": expiry,
            "dte": dte,
            "instrument_name": f"X{int(s)}{'CE' if otype == 'call' else 'PE'}",
        }
        for s in strikes
    ]


def test_atm_call_for_bull():
    chain = _chain([80, 90, 100, 110, 120], "call")
    pick = pick_strike(chain, spot=102, direction="long", moneyness="ATM")
    assert isinstance(pick, OptionPick)
    assert pick.strike == 100 and pick.option_type == "CE"


def test_itm1_put_for_bear():
    chain = _chain([80, 90, 100, 110, 120], "put")
    pick = pick_strike(chain, spot=102, direction="short", moneyness="ITM1")
    # PUT ITM = strike ABOVE spot; ITM1 = one step in-the-money
    assert pick.strike == 110 and pick.option_type == "PE"


def test_itm1_call_steps_below_spot():
    chain = _chain([80, 90, 100, 110, 120], "call")
    pick = pick_strike(chain, spot=102, direction="long", moneyness="ITM1")
    # CALL ITM = strike BELOW spot
    assert pick.strike == 90 and pick.option_type == "CE"


def test_no_itm_available_returns_none():
    chain = _chain([120, 130], "call")  # all strikes above spot → no ITM calls
    assert pick_strike(chain, spot=100, direction="long", moneyness="ITM2") is None
    # ATM still resolves to the nearest strike
    assert pick_strike(chain, spot=100, direction="long", moneyness="ATM") is not None


def test_otm1_call_steps_above_spot():
    chain = _chain([80, 90, 100, 110, 120], "call")
    pick = pick_strike(chain, spot=102, direction="long", moneyness="OTM1")
    # CALL OTM = strike ABOVE spot; OTM1 = one step out-of-the-money
    assert pick.strike == 110 and pick.option_type == "CE"


def test_otm2_call_two_steps_above_spot():
    chain = _chain([80, 90, 100, 110, 120], "call")
    pick = pick_strike(chain, spot=102, direction="long", moneyness="OTM2")
    assert pick.strike == 120 and pick.option_type == "CE"


def test_otm1_put_steps_below_spot():
    chain = _chain([80, 90, 100, 110, 120], "put")
    pick = pick_strike(chain, spot=102, direction="short", moneyness="OTM1")
    # PUT OTM = strike BELOW spot
    assert pick.strike == 90 and pick.option_type == "PE"


def test_no_otm_available_returns_none():
    chain = _chain([70, 80, 90], "call")  # all strikes below spot → no OTM calls
    assert pick_strike(chain, spot=100, direction="long", moneyness="OTM1") is None
    # ATM still resolves to the nearest strike
    assert pick_strike(chain, spot=100, direction="long", moneyness="ATM") is not None


def test_nearest_expiry_and_min_dte_filter():
    near = _chain([100], "call", expiry="2026-06-19", dte=3)
    far = _chain([100], "call", expiry="2026-07-31", dte=45)
    expired = _chain([100], "call", expiry="2026-06-13", dte=0)
    pick = pick_strike(near + far + expired, spot=100, direction="long",
                       moneyness="ATM", min_dte=1)
    assert pick is not None and pick.dte == 3  # nearest expiry above the DTE floor


def test_pick_strike_carries_instrument_token():
    chain = [{"strike": 100.0, "option_type": "call", "expiry_date": "2026-06-26",
              "dte": 8, "instrument_name": "X100CE", "token": 999}]
    pick = pick_strike(chain, spot=100, direction="long", moneyness="ATM")
    assert pick.token == 999


def test_pick_contracts_resolves_both_ce_and_pe_per_moneyness():
    from app.services.kite_engine.strikes import pick_contracts
    chain = _chain([90, 100, 110], "call") + _chain([90, 100, 110], "put")
    picks = pick_contracts(chain, spot=100, moneynesses=["ATM", "ITM1"])
    by = {(m, p.option_type): p.strike for m, p in picks}
    # ATM is the nearest strike for both sides
    assert by[("ATM", "CE")] == 100 and by[("ATM", "PE")] == 100
    # ITM is in-the-money for THAT side: CALL ITM below spot, PUT ITM above spot
    assert by[("ITM1", "CE")] == 90 and by[("ITM1", "PE")] == 110


def test_chain_rows_for_filters_and_computes_dte():
    from datetime import date
    from app.services.kite_engine.strikes import chain_rows_for

    dump = [
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE25JUN3000CE", "instrument_type": "CE",
         "strike": 3000, "expiry": "2026-06-26", "lot_size": 250, "instrument_token": 88001},
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE25JUN3000PE", "instrument_type": "PE",
         "strike": 3000, "expiry": "2026-06-26", "lot_size": 250},
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE25JUNFUT", "instrument_type": "FUT",
         "strike": 0, "expiry": "2026-06-26"},
        {"name": "INFY", "tradingsymbol": "INFY25JUN1500CE", "instrument_type": "CE",
         "strike": 1500, "expiry": "2026-06-26"},
    ]
    rows = chain_rows_for(dump, "RELIANCE", date(2026, 6, 13))
    assert len(rows) == 2  # only RELIANCE CE/PE (FUT excluded, INFY excluded)
    r = rows[0]
    assert r["dte"] == 13 and r["option_type"] in ("call", "put")
    assert r["token"] == 88001  # instrument_token carried through for candle fetch
    # feeds straight into pick_strike
    pick = pick_strike(rows, spot=3010, direction="long", moneyness="ATM")
    assert pick is not None and pick.strike == 3000 and pick.option_type == "CE"


def test_chain_rows_for_resolves_sensex_regardless_of_name_field():
    """BSE index options carry a SHORT CODE in `name` (SENSEX→BSX). Resolution must
    work whether Kite labels them "BSX", "SENSEX", or anything else — the
    tradingsymbol prefix ("SENSEX25…") is the bulletproof net."""
    from datetime import date
    from app.services.kite_engine.strikes import chain_rows_for

    for name_field in ("BSX", "SENSEX", "WHATEVER"):
        dump = [
            {"name": name_field, "tradingsymbol": "SENSEX2561876000CE", "instrument_type": "CE",
             "strike": 76000, "expiry": "2026-06-18", "lot_size": 20, "instrument_token": 9001},
            {"name": name_field, "tradingsymbol": "SENSEX2561876000PE", "instrument_type": "PE",
             "strike": 76000, "expiry": "2026-06-18", "lot_size": 20, "instrument_token": 9002},
            # an unrelated BFO name must NOT leak in
            {"name": "BKX", "tradingsymbol": "BANKEX2561862000CE", "instrument_type": "CE",
             "strike": 62000, "expiry": "2026-06-18"},
        ]
        rows = chain_rows_for(dump, "SENSEX", date(2026, 6, 15))
        assert len(rows) == 2, f"name_field={name_field!r}"
        assert {r["token"] for r in rows} == {9001, 9002}


def test_chain_prefix_match_does_not_over_match_sibling_indices():
    """The tradingsymbol-prefix net requires a DIGIT after the name, so "NIFTY"
    never swallows BANKNIFTY / FINNIFTY / NIFTYNXT50 options."""
    from datetime import date
    from app.services.kite_engine.strikes import chain_rows_for

    dump = [
        {"name": "NIFTY", "tradingsymbol": "NIFTY2561824500CE", "instrument_type": "CE",
         "strike": 24500, "expiry": "2026-06-18", "instrument_token": 1},
        {"name": "BANKNIFTY", "tradingsymbol": "BANKNIFTY2561854000CE", "instrument_type": "CE",
         "strike": 54000, "expiry": "2026-06-18", "instrument_token": 2},
        {"name": "NIFTYNXT50", "tradingsymbol": "NIFTYNXT502561868000CE", "instrument_type": "CE",
         "strike": 68000, "expiry": "2026-06-18", "instrument_token": 3},
    ]
    rows = chain_rows_for(dump, "NIFTY", date(2026, 6, 15))
    assert [r["token"] for r in rows] == [1]  # only the real NIFTY option
