import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.nifty_orb_execution import _conservative_quantity, _parse_timestamp, _quote_age

IST = ZoneInfo("Asia/Kolkata")


def test_conservative_quantity_is_lot_aligned_and_never_exceeds_premium_budget():
    assert _conservative_quantity(225, 75, 40.0, 3000.0) == 0
    assert _conservative_quantity(225, 75, 20.0, 3000.0) == 150
    assert _conservative_quantity(150, 75, 20.0, 3000.0) == 150


def test_timestamp_parser_normalizes_naive_and_utc_timestamps():
    naive = _parse_timestamp("2026-08-19T10:00:00")
    utc = _parse_timestamp("2026-08-19T04:30:00Z")
    assert naive.tzinfo is not None
    assert utc.tzinfo is not None
    assert naive.astimezone(ZoneInfo("UTC")) == utc.astimezone(ZoneInfo("UTC"))


def test_quote_age_rejects_missing_timestamp_semantically():
    assert _quote_age(None) is None


def test_quote_age_is_non_negative_for_recent_quote():
    now = datetime.now(IST)
    assert 0 <= _quote_age(now.isoformat()) < 2
