from __future__ import annotations

from datetime import date, datetime

import pytest

from app.services.navigator import calendar


class TestCoverageAndFailClosed:
    def test_covered_year_is_2026(self):
        assert 2026 in calendar.COVERED_YEARS

    def test_uncovered_year_raises_calendar_unknown(self):
        with pytest.raises(calendar.CalendarUnknownError):
            calendar.is_trading_day(date(2027, 1, 4))

    def test_uncovered_past_year_also_raises(self):
        with pytest.raises(calendar.CalendarUnknownError):
            calendar.is_trading_day(date(2024, 1, 4))


class TestTradingDayAndHolidays:
    def test_ordinary_weekday_is_a_trading_day(self):
        assert calendar.is_trading_day(date(2026, 7, 27)) is True  # Monday

    def test_weekend_is_not_a_trading_day(self):
        assert calendar.is_trading_day(date(2026, 8, 1)) is False  # Saturday
        assert calendar.is_trading_day(date(2026, 8, 2)) is False  # Sunday

    def test_republic_day_is_a_holiday(self):
        assert calendar.is_trading_day(date(2026, 1, 26)) is False

    def test_christmas_is_a_holiday(self):
        assert calendar.is_trading_day(date(2026, 12, 25)) is False

    def test_muhurat_sunday_is_not_treated_as_a_trading_day(self):
        # 2026-11-08 is a bonus Sunday session, not a regular trading day —
        # Navigator does not scan it.
        assert calendar.is_trading_day(date(2026, 11, 8)) is False


class TestSessionBounds:
    def test_session_bounds_are_915_to_1530_ist(self):
        open_dt, close_dt = calendar.session_bounds_ist(date(2026, 7, 27))
        assert (open_dt.hour, open_dt.minute) == (9, 15)
        assert (close_dt.hour, close_dt.minute) == (15, 30)
        assert str(open_dt.tzinfo) == str(calendar.IST)

    def test_session_bounds_rejects_a_holiday(self):
        with pytest.raises(ValueError):
            calendar.session_bounds_ist(date(2026, 1, 26))


class TestIsMarketOpenAt:
    def test_open_during_session(self):
        dt = datetime(2026, 7, 27, 10, 0, tzinfo=calendar.IST)
        ts_ms = int(dt.timestamp() * 1000)
        assert calendar.is_market_open_at(ts_ms) is True

    def test_closed_before_open(self):
        dt = datetime(2026, 7, 27, 8, 0, tzinfo=calendar.IST)
        ts_ms = int(dt.timestamp() * 1000)
        assert calendar.is_market_open_at(ts_ms) is False

    def test_closed_after_close(self):
        dt = datetime(2026, 7, 27, 16, 0, tzinfo=calendar.IST)
        ts_ms = int(dt.timestamp() * 1000)
        assert calendar.is_market_open_at(ts_ms) is False

    def test_closed_on_a_holiday_even_during_session_hours(self):
        dt = datetime(2026, 12, 25, 10, 0, tzinfo=calendar.IST)
        ts_ms = int(dt.timestamp() * 1000)
        assert calendar.is_market_open_at(ts_ms) is False


class TestNextTradingDay:
    def test_skips_weekend(self):
        # Friday 2026-07-31 -> next trading day should be Monday 2026-08-03
        assert calendar.next_trading_day(date(2026, 7, 31)) == date(2026, 8, 3)

    def test_skips_a_holiday(self):
        # day before Republic Day (a Sunday, 2026-01-25) -> skip weekend AND holiday
        result = calendar.next_trading_day(date(2026, 1, 23))  # Friday
        assert result == date(2026, 1, 27)  # Tue (Mon 26th is Republic Day)


class TestEntryDelayAndExpiryClose:
    def test_entry_delay_cutoff_adds_minutes_to_open(self):
        cutoff = calendar.entry_delay_cutoff_ist(date(2026, 7, 27), 5)
        assert (cutoff.hour, cutoff.minute) == (9, 20)

    def test_expiry_close_defaults_to_session_close(self):
        close_dt = calendar.expiry_close_ist(date(2026, 7, 27))
        assert (close_dt.hour, close_dt.minute) == (15, 30)
