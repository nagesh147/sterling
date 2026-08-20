import asyncio

import pytest

from app.services import nifty_orb_options_runner as runner


@pytest.mark.asyncio
async def test_runner_start_is_singleton(monkeypatch):
    """start() schedules on the running loop, exactly as the startup hook does."""
    async def idle():
        await asyncio.sleep(60)

    monkeypatch.setattr(runner, "run_forever", idle)
    runner.stop()
    first = runner.start()
    second = runner.start()
    assert first is second
    runner.stop()
    assert first.cancelled() or first.cancelling() or first.done()


def test_market_open_fails_closed_when_calendar_unavailable(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "app.services.navigator.calendar":
            raise ImportError("calendar unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    assert runner._is_verified_market_open() is False


def test_runner_does_not_execute_when_market_closed(monkeypatch):
    called = False

    async def fake_users():
        nonlocal called
        called = True

    monkeypatch.setattr(runner, "_is_verified_market_open", lambda: False)
    asyncio.run(runner._tick())
    assert called is False
