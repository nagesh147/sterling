from datetime import date

from app.services.kite_engine.strikes import (
    OptionPick,
    _expiry_date_set,
    chain_rows_for,
    pick_contracts,
    pick_strike,
)


def _chain(strikes, otype, expiry="2026-06-30", dte=8):
    suffix = "CE" if otype == "call" else "PE"
    return [
        {
            "strike": float(s),
            "option_type": otype,
            "expiry_date": expiry,
            "dte": dte,
            "instrument_name": f"X{expiry.replace('-', '')}{int(s)}{suffix}",
        }
        for s in strikes
    ]


def test_atm_call_for_bull():
    pick = pick_strike(_chain([80, 90, 100, 110, 120], "call"), spot=102, direction="long")
    assert isinstance(pick, OptionPick)
    assert pick.strike == 100 and pick.option_type == "CE"


def test_call_and_put_moneyness_directions():
    calls = _chain([80, 90, 100, 110, 120], "call")
    puts = _chain([80, 90, 100, 110, 120], "put")
    # Rank 1 is the nearest listed strike on the requested side of spot.
    assert pick_strike(calls, spot=102, direction="long", moneyness="ITM1").strike == 100
    assert pick_strike(calls, spot=102, direction="long", moneyness="OTM1").strike == 110
    assert pick_strike(puts, spot=102, direction="short", moneyness="ITM1").strike == 110
    assert pick_strike(puts, spot=102, direction="short", moneyness="OTM1").strike == 100


def test_requested_depth_clamps_to_same_side_of_listed_ladder():
    calls = _chain([80, 90, 100, 110, 120], "call")
    puts = _chain([80, 90, 100, 110, 120], "put")
    assert pick_strike(calls, spot=102, direction="long", moneyness="ITM20").strike == 80
    assert pick_strike(calls, spot=102, direction="long", moneyness="OTM5").strike == 120
    assert pick_strike(puts, spot=102, direction="short", moneyness="ITM20").strike == 120
    assert pick_strike(puts, spot=102, direction="short", moneyness="OTM5").strike == 80


def test_nearest_expiry_and_min_dte_filter():
    near = _chain([100], "call", expiry="2026-06-23", dte=3)
    far = _chain([100], "call", expiry="2026-07-28", dte=38)
    expired = _chain([100], "call", expiry="2026-06-16", dte=0)
    pick = pick_strike(near + far + expired, spot=100, direction="long", min_dte=1)
    assert pick is not None and pick.dte == 3


def test_expiry_classification_uses_actual_listed_dates_not_weekday():
    # Synthetic dates prove classification follows the dump exactly; they do not
    # assert a historical exchange holiday or a derived weekday rule.
    chain = (
        _chain([100], "call", "2026-06-02", 1)
        + _chain([100], "call", "2026-06-09", 8)
        + _chain([100], "call", "2026-06-16", 15)
        + _chain([100], "call", "2026-06-23", 22)
        + _chain([100], "call", "2026-06-29", 28)
        + _chain([100], "call", "2026-07-28", 57)
    )
    labels = _expiry_date_set(chain, date(2026, 6, 1))
    assert labels["2026-06-02"] == {"weekly"}
    assert labels["2026-06-23"] == {"weekly"}
    assert labels["2026-06-29"] == {"monthly"}
    assert labels["2026-07-28"] == {"monthly"}


def test_monthly_only_chain_never_invents_weeklies():
    chain = (
        _chain([100], "call", "2026-06-30", 20)
        + _chain([100], "call", "2026-07-28", 48)
        + _chain([100], "call", "2026-08-25", 76)
    )
    labels = _expiry_date_set(chain, date(2026, 6, 10))
    assert all(v == {"monthly"} for v in labels.values())
    assert pick_strike(
        chain, spot=100, direction="long", expiry_type="weekly", expiry_rank=0,
        today=date(2026, 6, 10),
    ) is None


def test_w1_to_w4_and_m1_to_m2_rank_resolution():
    expiries = [
        ("2026-06-02", 1), ("2026-06-09", 8), ("2026-06-16", 15),
        ("2026-06-23", 22), ("2026-06-30", 29), ("2026-07-28", 57),
    ]
    chain = []
    for expiry, dte in expiries:
        chain += _chain([90, 100, 110], "call", expiry, dte)
        chain += _chain([90, 100, 110], "put", expiry, dte)

    for rank, expiry in enumerate([e[0] for e in expiries[:4]]):
        pick = pick_strike(
            chain, spot=100, direction="long", expiry_type="weekly",
            expiry_rank=rank, today=date(2026, 6, 1),
        )
        assert pick is not None and pick.expiry == expiry

    for rank, expiry in enumerate(["2026-06-30", "2026-07-28"]):
        pick = pick_strike(
            chain, spot=100, direction="long", expiry_type="monthly",
            expiry_rank=rank, today=date(2026, 6, 1),
        )
        assert pick is not None and pick.expiry == expiry


def test_pick_contracts_resolves_both_sides_across_selected_series():
    chain = []
    for expiry, dte in [("2026-06-02", 1), ("2026-06-09", 8), ("2026-06-30", 29)]:
        chain += _chain([90, 100, 110], "call", expiry, dte)
        chain += _chain([90, 100, 110], "put", expiry, dte)
    picks = pick_contracts(
        chain,
        spot=100,
        moneynesses=["ATM", "ITM1", "OTM1"],
        expiry_ranks_by_type={"weekly": [0, 1], "monthly": [0]},
        today=date(2026, 6, 1),
    )
    assert {p.expiry for _, p in picks} == {"2026-06-02", "2026-06-09", "2026-06-30"}
    assert {p.option_type for _, p in picks} == {"CE", "PE"}
    assert len(picks) == 18


def test_pick_strike_carries_instrument_token():
    chain = [{
        "strike": 100.0, "option_type": "call", "expiry_date": "2026-06-30",
        "dte": 8, "instrument_name": "X100CE", "token": 999,
    }]
    assert pick_strike(chain, spot=100, direction="long").token == 999


def test_chain_rows_for_filters_computes_dte_and_skips_expired():
    dump = [
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE26JUN3000CE", "instrument_type": "CE",
         "strike": 3000, "expiry": "2026-06-30", "lot_size": 250, "instrument_token": 88001},
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE26JUN3000PE", "instrument_type": "PE",
         "strike": 3000, "expiry": "2026-06-30", "lot_size": 250},
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE26JUNFUT", "instrument_type": "FUT",
         "strike": 0, "expiry": "2026-06-30"},
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE26MAY3000CE", "instrument_type": "CE",
         "strike": 3000, "expiry": "2026-05-26"},
        {"name": "INFY", "tradingsymbol": "INFY26JUN1500CE", "instrument_type": "CE",
         "strike": 1500, "expiry": "2026-06-30"},
    ]
    rows = chain_rows_for(dump, "RELIANCE", date(2026, 6, 17))
    assert len(rows) == 2
    assert rows[0]["dte"] == 13
    assert rows[0]["token"] == 88001


def test_chain_rows_for_resolves_sensex_alias_and_prefix():
    for name_field in ("BSX", "SENSEX", "WHATEVER"):
        dump = [
            {"name": name_field, "tradingsymbol": "SENSEX2672876000CE", "instrument_type": "CE",
             "strike": 76000, "expiry": "2026-07-28", "instrument_token": 9001},
            {"name": name_field, "tradingsymbol": "SENSEX2672876000PE", "instrument_type": "PE",
             "strike": 76000, "expiry": "2026-07-28", "instrument_token": 9002},
            {"name": "BKX", "tradingsymbol": "BANKEX2672862000CE", "instrument_type": "CE",
             "strike": 62000, "expiry": "2026-07-28"},
        ]
        rows = chain_rows_for(dump, "SENSEX", date(2026, 6, 15))
        assert {r["token"] for r in rows} == {9001, 9002}


def test_chain_prefix_match_does_not_overmatch_sibling_indices():
    dump = [
        {"name": "NIFTY", "tradingsymbol": "NIFTY2672824500CE", "instrument_type": "CE",
         "strike": 24500, "expiry": "2026-07-28", "instrument_token": 1},
        {"name": "BANKNIFTY", "tradingsymbol": "BANKNIFTY2672854000CE", "instrument_type": "CE",
         "strike": 54000, "expiry": "2026-07-28", "instrument_token": 2},
        {"name": "NIFTYNXT50", "tradingsymbol": "NIFTYNXT502672868000CE", "instrument_type": "CE",
         "strike": 68000, "expiry": "2026-07-28", "instrument_token": 3},
    ]
    rows = chain_rows_for(dump, "NIFTY", date(2026, 6, 15))
    assert [r["token"] for r in rows] == [1]
