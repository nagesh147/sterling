from datetime import date

from app.engines.adaptive_edge.option_ladder import (
    AE_DEFAULT_LADDER,
    build_snapshot_signals,
    expand_spot_signal,
)


def _chain(strikes, otype, expiry="2026-08-27", dte=12):
    suffix = "CE" if otype == "call" else "PE"
    return [
        {
            "strike": float(s),
            "option_type": otype,
            "expiry_date": expiry,
            "dte": dte,
            "instrument_name": f"NIFTY26AUG{int(s)}{suffix}",
        }
        for s in strikes
    ]


FIXTURE_CHAIN = _chain(
    [24300, 24350, 24400, 24450, 24500, 24550, 24600, 24650, 24700],
    "call",
) + _chain(
    [24300, 24350, 24400, 24450, 24500, 24550, 24600, 24650, 24700],
    "put",
)


def test_buy_signal_expands_ce_atm_2itm_2otm():
    legs = expand_spot_signal(
        spot=24500,
        side="BUY",
        option_name="NIFTY",
        option_rows=FIXTURE_CHAIN,
        moneynesses=AE_DEFAULT_LADDER,
        stop_points=80,
        trail_points=40,
        today=date(2026, 8, 15),
    )
    assert [leg.moneyness for leg in legs] == ["ITM2", "ITM1", "ATM", "OTM1", "OTM2"]
    assert {leg.option_type for leg in legs} == {"CE"}
    assert all(leg.option_symbol for leg in legs)
    assert legs[2].strike == 24500
    assert legs[0].strike == 24400
    assert legs[4].strike == 24600
    assert legs[2].entry_premium is not None
    assert legs[2].stop_premium is not None


def test_sell_signal_expands_pe():
    legs = expand_spot_signal(
        spot=24500,
        side="SELL",
        option_name="NIFTY",
        option_rows=FIXTURE_CHAIN,
        moneynesses=AE_DEFAULT_LADDER,
        stop_points=80,
        trail_points=40,
        today=date(2026, 8, 15),
    )
    assert {leg.option_type for leg in legs} == {"PE"}
    assert legs[2].strike == 24500
    assert legs[0].strike == 24600
    assert legs[4].strike == 24400


def test_empty_chain_does_not_invent_symbols():
    legs = expand_spot_signal(
        spot=24500,
        side="BUY",
        option_name="NIFTY",
        option_rows=[],
        moneynesses=AE_DEFAULT_LADDER,
        stop_points=80,
        trail_points=40,
        today=date(2026, 8, 15),
    )
    assert [leg.moneyness for leg in legs] == ["ITM2", "ITM1", "ATM", "OTM1", "OTM2"]
    assert all(leg.option_symbol == "" for leg in legs)
    assert all(leg.resolution_reason for leg in legs)
    assert legs[2].strike == 24500


def test_snapshot_signals_expand_open_leg_and_mark_missing_tape():
    signals = build_snapshot_signals(
        legs=[
            {
                "symbol": "NIFTY-I",
                "side": "BUY",
                "entry_price": 24500,
                "entry_time": "2026-08-14T08:38:00+00:00",
                "exit_time": None,
                "flattened": False,
                "quantity": 1,
                "entry_score": 0.62,
                "entry_poc": 24405,
                "entry_vwap": 24409.84,
            }
        ],
        session={"last_poc": 24405, "last_vwap": 24409.84, "last_cvd": 32055},
        settings={
            "symbol": "NIFTY-I",
            "scan_indices": ["NIFTY 50", "NIFTY BANK", "NIFTY FIN SERVICE", "SENSEX"],
            "strike_moneyness": list(AE_DEFAULT_LADDER),
            "stop_points": 80,
            "trail_points": 40,
        },
        option_rows=FIXTURE_CHAIN,
        today=date(2026, 8, 15),
    )
    scanned = [item for item in signals if item["scanned"]]
    skipped = [item for item in signals if not item["scanned"]]
    assert len(scanned) == 1
    assert scanned[0]["option_type"] == "CE"
    assert [leg["moneyness"] for leg in scanned[0]["legs"]] == list(AE_DEFAULT_LADDER)
    assert {item["skip_reason"] for item in skipped} == {"no tape"}
    assert {item["underlying"] for item in skipped} == {
        "NIFTY BANK",
        "NIFTY FIN SERVICE",
        "SENSEX",
    }


def test_snapshot_uses_live_spot_scans_for_other_indices():
    signals = build_snapshot_signals(
        legs=[{
            "symbol": "NIFTY-I",
            "side": "BUY",
            "entry_price": 24500,
            "entry_time": "2026-08-14T08:38:00+00:00",
            "flattened": False,
            "quantity": 1,
        }],
        session={},
        settings={
            "symbol": "NIFTY-I",
            "scan_indices": ["NIFTY 50", "NIFTY BANK", "SENSEX"],
            "strike_moneyness": list(AE_DEFAULT_LADDER),
            "stop_points": 80,
            "trail_points": 40,
        },
        option_rows=[],
        spot_scans={
            "NIFTY BANK": {
                "underlying": "NIFTY BANK",
                "source": "spot",
                "direction": "short",
                "spot": 57214.8,
                "is_active": True,
                "timestamp_ms": 1786750154420,
                "legs": [
                    {"moneyness": "ITM2", "option_type": "PE", "option_symbol": "BANKNIFTY26AUG57400PE", "strike": 57400, "expiry": "2026-08-25", "lot_size": 30, "token": 1, "premium_spot": 590.25, "entry_sl": 290.03, "premium_sl": 430.96},
                    {"moneyness": "ITM1", "option_type": "PE", "option_symbol": "BANKNIFTY26AUG57300PE", "strike": 57300, "expiry": "2026-08-25", "lot_size": 30, "token": 2, "premium_spot": 544.05, "entry_sl": 260.32, "premium_sl": 393.51},
                    {"moneyness": "ATM", "option_type": "PE", "option_symbol": "BANKNIFTY26AUG57200PE", "strike": 57200, "expiry": "2026-08-25", "lot_size": 30, "token": 3, "premium_spot": 501.25, "entry_sl": 233.72, "premium_sl": 359.30},
                    {"moneyness": "OTM1", "option_type": "PE", "option_symbol": "BANKNIFTY26AUG57100PE", "strike": 57100, "expiry": "2026-08-25", "lot_size": 30, "token": 4, "premium_spot": 458.60, "entry_sl": 207.08, "premium_sl": 325.15},
                    {"moneyness": "OTM2", "option_type": "PE", "option_symbol": "BANKNIFTY26AUG57000PE", "strike": 57000, "expiry": "2026-08-25", "lot_size": 30, "token": 5, "premium_spot": 420.00, "entry_sl": 184.07, "premium_sl": 294.82},
                ],
            },
            "SENSEX": {
                "underlying": "SENSEX",
                "source": "spot",
                "direction": "short",
                "spot": 78106.0,
                "is_active": False,
                "timestamp_ms": 1786750154420,
            },
        },
        today=date(2026, 8, 15),
    )
    by_name = {item["underlying"]: item for item in signals}
    assert set(by_name) == {"NIFTY 50", "NIFTY BANK", "SENSEX"}
    assert by_name["NIFTY BANK"]["scanned"] is True
    assert by_name["NIFTY BANK"]["option_type"] == "PE"
    assert by_name["NIFTY BANK"]["scan_origin"] == "spot_scan"
    assert [leg["moneyness"] for leg in by_name["NIFTY BANK"]["legs"]] == list(AE_DEFAULT_LADDER)
    atm = next(leg for leg in by_name["NIFTY BANK"]["legs"] if leg["moneyness"] == "ATM")
    assert atm["option_symbol"] == "BANKNIFTY26AUG57200PE"
    assert atm["entry_premium"] == 501.25
    assert atm["stop_premium"] == 233.72
    assert atm["trail_premium"] == 359.30
    assert by_name["SENSEX"]["option_type"] == "PE"
    assert all(item.get("skip_reason") != "no tape" for item in signals)


def test_snapshot_scans_stock_contracts_when_enabled():
    signals = build_snapshot_signals(
        legs=[],
        session={},
        settings={
            "symbol": "NIFTY-I",
            "scan_indices": ["NIFTY 50"],
            "scan_stock_contracts": True,
            "scan_stocks": ["RELIANCE", "INFY"],
            "strike_moneyness": list(AE_DEFAULT_LADDER),
            "stop_points": 20,
            "trail_points": 10,
        },
        option_rows=[],
        spot_scans={
            "RELIANCE": {
                "underlying": "RELIANCE",
                "source": "spot",
                "direction": "long",
                "spot": 2980.5,
                "is_active": True,
                "timestamp_ms": 1786750154420,
                "legs": [
                    {"moneyness": "ATM", "option_type": "CE", "option_symbol": "RELIANCE26AUG3000CE", "strike": 3000, "expiry": "2026-08-25", "lot_size": 250, "token": 101, "premium_spot": 62.5, "ltp": 65.0},
                ],
            }
        },
        today=date(2026, 8, 15),
    )
    by_name = {item["underlying"]: item for item in signals}
    assert "RELIANCE" in by_name
    assert by_name["RELIANCE"]["scanned"] is True
    assert by_name["RELIANCE"]["side"] == "BUY"
    assert by_name["RELIANCE"]["option_type"] == "CE"
    assert len(by_name["RELIANCE"]["legs"]) == 5
    atm = next(leg for leg in by_name["RELIANCE"]["legs"] if leg["moneyness"] == "ATM")
    assert atm["option_symbol"] == "RELIANCE26AUG3000CE"
    assert atm["entry_premium"] == 62.5
    assert atm["ltp"] == 65.0
    # INFY had no live row, so it is unscanned
    assert "INFY" in by_name
    assert by_name["INFY"]["scanned"] is False
    assert by_name["INFY"]["skip_reason"] == "no tape"
