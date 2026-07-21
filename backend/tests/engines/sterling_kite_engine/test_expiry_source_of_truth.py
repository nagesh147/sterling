"""Expiry source-of-truth integration tests.

Dates in these fixtures are intentionally synthetic. They do not claim a real
exchange holiday calendar. Their purpose is to prove that production resolution
uses the dates listed in the instrument dump and never derives a date from a
weekday assumption.
"""
from datetime import date

from app.services.kite_engine.strikes import (
    _expiry_date_set,
    chain_rows_for,
    pick_strike,
)


def _row(expiry: str, *, strike: float = 100.0, token: int = 1) -> dict:
    return {
        "strike": strike,
        "option_type": "call",
        "expiry_date": expiry,
        "dte": (date.fromisoformat(expiry) - date(2026, 6, 1)).days,
        "instrument_name": f"TEST{expiry.replace('-', '')}CE",
        "token": token,
    }


def test_non_tuesday_listed_date_is_preserved_exactly():
    chain = [
        _row("2026-06-02"),
        _row("2026-06-09"),
        _row("2026-06-16"),
        _row("2026-06-23"),
        _row("2026-06-29"),  # synthetic shifted date; not a real-holiday assertion
        _row("2026-07-28"),
    ]
    labels = _expiry_date_set(chain, date(2026, 6, 1))
    assert labels["2026-06-29"] == {"monthly"}
    pick = pick_strike(
        chain,
        spot=100,
        direction="long",
        expiry_type="monthly",
        expiry_rank=0,
        today=date(2026, 6, 1),
    )
    assert pick is not None
    assert pick.expiry == "2026-06-29"


def test_monthly_only_dump_cannot_create_a_weekly_contract():
    chain = [_row("2026-06-30"), _row("2026-07-28"), _row("2026-08-25")]
    assert pick_strike(
        chain,
        spot=100,
        direction="long",
        expiry_type="weekly",
        expiry_rank=0,
        today=date(2026, 6, 1),
    ) is None


def test_raw_kite_expiry_field_survives_chain_conversion_unchanged():
    dump = [{
        "name": "TEST",
        "tradingsymbol": "TEST26X100CE",
        "instrument_type": "CE",
        "strike": 100,
        "expiry": "2026-06-29",
        "instrument_token": 9001,
        "lot_size": 50,
    }]
    rows = chain_rows_for(dump, "TEST", date(2026, 6, 1))
    assert len(rows) == 1
    assert rows[0]["expiry_date"] == dump[0]["expiry"]
    assert rows[0]["token"] == 9001
