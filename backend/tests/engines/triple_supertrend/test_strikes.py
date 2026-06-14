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


def test_nearest_expiry_and_min_dte_filter():
    near = _chain([100], "call", expiry="2026-06-19", dte=3)
    far = _chain([100], "call", expiry="2026-07-31", dte=45)
    expired = _chain([100], "call", expiry="2026-06-13", dte=0)
    pick = pick_strike(near + far + expired, spot=100, direction="long",
                       moneyness="ATM", min_dte=1)
    assert pick is not None and pick.dte == 3  # nearest expiry above the DTE floor


def test_chain_rows_for_filters_and_computes_dte():
    from datetime import date
    from app.services.kite_engine.strikes import chain_rows_for

    dump = [
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE25JUN3000CE", "instrument_type": "CE",
         "strike": 3000, "expiry": "2026-06-26", "lot_size": 250},
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
    # feeds straight into pick_strike
    pick = pick_strike(rows, spot=3010, direction="long", moneyness="ATM")
    assert pick is not None and pick.strike == 3000 and pick.option_type == "CE"
