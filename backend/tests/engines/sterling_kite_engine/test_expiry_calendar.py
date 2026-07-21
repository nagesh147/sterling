import json
from datetime import date

from app.services.kite_engine.expiry_calendar import (
    build_expiry_calendar,
    listed_expiry_series,
)


def _row(name: str, expiry: str, *, raw_name: str | None = None, side: str = "CE") -> dict:
    return {
        "name": raw_name or name,
        "tradingsymbol": f"{name}26{expiry.replace('-', '')}100{side}",
        "instrument_type": side,
        "expiry": expiry,
    }


def test_listed_series_preserves_exact_dates_and_classifies_month_end():
    rows = [
        _row("NIFTY", expiry)
        for expiry in (
            "2026-07-21", "2026-07-27",  # synthetic holiday-shifted month end
            "2026-08-04", "2026-08-11", "2026-08-18", "2026-08-25",
        )
    ]
    assert listed_expiry_series(rows, "NIFTY", today=date(2026, 7, 21)) == {
        "weekly": ["2026-07-21", "2026-08-04", "2026-08-11", "2026-08-18"],
        "monthly": ["2026-07-27", "2026-08-25"],
    }


def test_calendar_returns_concrete_index_and_stock_dates_without_rank_labels():
    nfo = [
        *[_row("NIFTY", expiry) for expiry in (
            "2026-07-21", "2026-07-28", "2026-08-04", "2026-08-11",
            "2026-08-18", "2026-08-25",
        )],
        _row("RELIANCE", "2026-07-21"),  # invalid weekly-like stock row must be ignored
        _row("RELIANCE", "2026-07-28"),
        _row("RELIANCE", "2026-08-25"),
        _row("TCS", "2026-07-28"),
        _row("TCS", "2026-08-25"),
    ]
    bfo = [
        _row("SENSEX", "2026-07-23", raw_name="BSX"),
        _row("SENSEX", "2026-07-30", raw_name="BSX"),
        _row("SENSEX", "2026-08-27", raw_name="BSX"),
    ]
    calendar = build_expiry_calendar(
        nfo_rows=nfo,
        bfo_rows=bfo,
        index_definitions=[
            {"name": "NIFTY 50", "option_name": "NIFTY", "option_exchange": "NFO"},
            {"name": "SENSEX", "option_name": "SENSEX", "option_exchange": "BFO"},
        ],
        stock_names=["RELIANCE", "TCS"],
        today=date(2026, 7, 21),
    )

    assert calendar["indices"][0]["weekly"][0] == "2026-07-21"
    assert calendar["indices"][0]["monthly"] == ["2026-07-28", "2026-08-25"]
    assert calendar["indices"][1]["weekly"] == ["2026-07-23"]
    assert calendar["indices"][1]["monthly"] == ["2026-07-30", "2026-08-27"]
    assert {tuple(stock["monthly"]) for stock in calendar["stocks"]} == {
        ("2026-07-28", "2026-08-25"),
    }
    assert all(stock["weekly"] == [] for stock in calendar["stocks"])
    assert not any(code in json.dumps(calendar) for code in ("W1", "W2", "M1", "M2"))


def test_expired_invalid_and_duplicate_option_sides_never_leak_into_calendar():
    rows = [
        _row("NIFTY", "2026-07-14"),
        _row("NIFTY", "not-a-date"),
        _row("NIFTY", "2026-07-28", side="CE"),
        _row("NIFTY", "2026-07-28", side="PE"),
        {**_row("NIFTY", "2026-08-25"), "instrument_type": "FUT"},
    ]
    assert listed_expiry_series(rows, "NIFTY", today=date(2026, 7, 21)) == {
        "weekly": [],
        "monthly": ["2026-07-28"],
    }


def test_year_rollover_keeps_chronological_weekly_and_monthly_ranks():
    rows = [
        _row("NIFTY", expiry)
        for expiry in ("2026-12-22", "2026-12-29", "2027-01-05", "2027-01-12", "2027-01-26")
    ]
    assert listed_expiry_series(rows, "NIFTY", today=date(2026, 12, 20)) == {
        "weekly": ["2026-12-22", "2027-01-05", "2027-01-12"],
        "monthly": ["2026-12-29", "2027-01-26"],
    }


def test_stock_names_are_normalised_and_deduplicated_in_input_order():
    calendar = build_expiry_calendar(
        nfo_rows=[_row("RELIANCE", "2026-07-28"), _row("TCS", "2026-07-28")],
        bfo_rows=[],
        index_definitions=[],
        stock_names=[" reliance ", "RELIANCE", "tcs"],
        today=date(2026, 7, 21),
    )
    assert [stock["name"] for stock in calendar["stocks"]] == ["RELIANCE", "TCS"]
