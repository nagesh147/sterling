import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services import nifty_orb_options_runner as runner

IST = ZoneInfo("Asia/Kolkata")


def test_runner_fails_closed_for_unverified_calendar_year(monkeypatch):
    class UnknownCalendar:
        def __call__(self, _ts):
            raise RuntimeError("calendar unknown")

    monkeypatch.setattr("app.services.navigator.calendar.is_market_open_at", UnknownCalendar())
    assert runner._is_verified_market_open() is False


def test_runner_uses_verified_calendar(monkeypatch):
    monkeypatch.setattr(
        "app.services.navigator.calendar.is_market_open_at",
        lambda _ts: True,
    )
    assert runner._is_verified_market_open() is True


@pytest.mark.asyncio
async def test_user_lock_suppresses_overlap(monkeypatch):
    lock = runner._lock_for("test-user")
    await lock.acquire()
    try:
        assert (await runner._run_user("test-user"))["status"] == "overlap_suppressed"
    finally:
        lock.release()


@pytest.mark.asyncio
async def test_start_is_single_flight(monkeypatch):
    async def never_finishes():
        await asyncio.Event().wait()

    monkeypatch.setattr(runner, "run_forever", never_finishes)
    first = runner.start()
    second = runner.start()
    assert first is second
    runner.stop()
    await asyncio.sleep(0)
