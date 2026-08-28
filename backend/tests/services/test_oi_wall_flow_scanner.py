"""Chain assembly, session OI baseline, and the BSE golden through the scanner."""
from __future__ import annotations

from app.engines.oi_wall_flow import OIWallFlowConfig, OIWallFlowStrategy
from app.services.oi_wall_flow_scanner import (attach_instrument, chain_rows_from_quotes,
                                               oi_chg_pct, reset_baselines,
                                               seed_oi_baseline)
from tests.engines.oi_wall_flow.conftest import BSE_ROWS


def setup_function():
    reset_baselines()


def _bse_contracts_and_quotes(day="2026-08-28"):
    """Quotes whose OI/LTP match the screenshot, plus a seeded session baseline
    so the *change* percentages match too."""
    contracts = []
    quotes = {}
    uid = "u1"
    for s, coi, coic, cltp, cltpc, pltp, pltpc, poi, poic in BSE_ROWS:
        ce = f"BSE26SEP{int(s)}CE"
        pe = f"BSE26SEP{int(s)}PE"
        contracts.append({
            "tradingsymbol": ce, "instrument_type": "CE", "strike": float(s),
            "expiry": "2026-09-29", "instrument_token": 1000 + int(s),
            "lot_size": 200, "tick_size": 0.05, "exchange": "NFO",
        })
        contracts.append({
            "tradingsymbol": pe, "instrument_type": "PE", "strike": float(s),
            "expiry": "2026-09-29", "instrument_token": 2000 + int(s),
            "lot_size": 200, "tick_size": 0.05, "exchange": "NFO",
        })
        # Invert the % change to recover the session-open OI, then seed it.
        ce_base = int(round(coi / (1 + coic / 100.0))) if coic != -100 else coi
        pe_base = int(round(poi / (1 + poic / 100.0))) if poic != -100 else poi
        seed_oi_baseline(uid, day, ce, max(ce_base, 1))
        seed_oi_baseline(uid, day, pe, max(pe_base, 1))
        ce_close = cltp / (1 + cltpc / 100.0) if cltpc != -100 else cltp
        pe_close = pltp / (1 + pltpc / 100.0) if pltpc != -100 else pltp
        quotes[f"NFO:{ce}"] = {
            "last_price": cltp, "oi": coi, "ohlc": {"close": ce_close},
        }
        quotes[f"NFO:{pe}"] = {
            "last_price": pltp, "oi": poi, "ohlc": {"close": pe_close},
        }
    quotes["NSE:BSE"] = {"last_price": 3392.50, "ohlc": {"close": 3328.0}}
    return contracts, quotes


def test_first_quote_of_the_day_is_zero_change():
    assert oi_chg_pct("u1", "2026-08-28", "FOO26SEP1CE", 1000) == 0.0
    assert round(oi_chg_pct("u1", "2026-08-28", "FOO26SEP1CE", 1100), 2) == 10.0


def test_bse_quotes_assemble_into_the_golden_chain():
    contracts, quotes = _bse_contracts_and_quotes()
    rows = chain_rows_from_quotes(contracts, quotes, "u1", "2026-08-28")
    by = {r.strike: r for r in rows}
    assert by[3500].call_ltp == 84.15
    assert by[3500].call_oi == 8136
    # Change recovers to the screenshot within a lot of rounding.
    assert abs(by[3500].call_oi_chg_pct - (-2.02)) < 0.15
    assert abs(by[3500].call_ltp_chg_pct - 25.22) < 0.05


def test_bse_chain_through_the_scanner_arms_3500_ce_never_a_pe():
    from app.engines.oi_wall_flow import ChainSnapshot
    contracts, quotes = _bse_contracts_and_quotes()
    rows = chain_rows_from_quotes(contracts, quotes, "u1", "2026-08-28")
    cfg = OIWallFlowConfig(max_premium_at_risk_inr=50_000).validate()
    snap = ChainSnapshot(underlying="BSE", spot=3392.50, expiry="2026-09-29",
                         rows=rows, days_to_expiry=32, lot_size=200)
    sig = attach_instrument(OIWallFlowStrategy(cfg).evaluate(snap), contracts)
    assert sig.state == "armed"
    assert sig.plan is not None
    assert sig.plan.option_type == "CE"
    assert sig.plan.strike == 3500
    assert sig.plan.instrument is not None
    assert sig.plan.instrument.tradingsymbol == "BSE26SEP3500CE"
    assert sig.plan.instrument.lot_size == 200


def test_sensex_is_not_an_option_name():
    from app.services.oi_wall_flow import option_name_of
    assert option_name_of("SENSEX") is None
    assert option_name_of("NIFTY 50") == "NIFTY"
    assert option_name_of("NIFTY BANK") == "BANKNIFTY"


def test_spot_quote_key_uses_the_index_display_name():
    from app.services.oi_wall_flow import spot_quote_key
    assert spot_quote_key("NIFTY") == "NSE:NIFTY 50"
    assert spot_quote_key("BANKNIFTY") == "NSE:NIFTY BANK"
    assert spot_quote_key("RELIANCE") == "NSE:RELIANCE"


def test_a_spot_quote_records_its_instrument_token():
    """Wall invalidation needs the cash/index tick, not just the option premium."""
    from app.services.oi_wall_flow_scanner import (_record_spots, last_spot_tokens,
                                                   last_spots, _token_of_quote)
    assert _token_of_quote({"instrument_token": 256265, "last_price": 24000}) == 256265
    assert _token_of_quote({}) == 0
    _record_spots("u1", ["NIFTY"], {
        "NSE:NIFTY 50": {"instrument_token": 256265, "last_price": 24100.5},
    })
    assert last_spot_tokens("u1") == {"NIFTY": 256265}
    assert last_spots("u1") == {"NIFTY": 24100.5}
